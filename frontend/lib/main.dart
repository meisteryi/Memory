import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:photo_manager/photo_manager.dart';
import 'package:photo_manager_image_provider/photo_manager_image_provider.dart';

import 'models/photo_model.dart';
import 'services/api_service.dart';
import 'widgets/chat_sheet.dart';
import 'widgets/result_view.dart';

void main() {
  runApp(const MemoryGalleryApp());
}

class MemoryGalleryApp extends StatelessWidget {
  const MemoryGalleryApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '기억 추적 스마트 갤러리',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF3F51B5), // 인디고 블루 포인트
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF8F9FA),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          elevation: 0,
          scrolledUnderElevation: 1,
          titleTextStyle: TextStyle(
            color: Colors.black87,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      home: const GalleryHomeScreen(),
    );
  }
}

class GalleryHomeScreen extends StatefulWidget {
  const GalleryHomeScreen({super.key});

  @override
  State<GalleryHomeScreen> createState() => _GalleryHomeScreenState();
}

class _GalleryHomeScreenState extends State<GalleryHomeScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _searchController = TextEditingController();

  // 기기 실제 갤러리 사진 목록
  List<AssetEntity> _deviceAssets = [];
  bool _hasPermission = false;

  // 백엔드 사진 목록 (폴백 또는 인덱싱 결과용)
  List<PhotoItem> _backendPhotos = [];
  bool _isLoading = true;
  String? _errorMessage;

  // AI 인덱싱 동기화 상태
  bool _isSyncing = false;
  int _syncedCount = 0;
  int _totalToSync = 0;

  // 검색 결과 상태
  SearchResponse? _activeSearchResult;

  @override
  void initState() {
    super.initState();
    _loadDeviceGalleryPhotos();
  }

  // 1. 기기 실제 갤러리 접근 및 권한 요청
  Future<void> _loadDeviceGalleryPhotos() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final PermissionState ps = await PhotoManager.requestPermissionExtend();
      if (ps.isAuth || ps.hasAccess) {
        _hasPermission = true;
        final List<AssetPathEntity> albums = await PhotoManager.getAssetPathList(
          type: RequestType.image,
          onlyAll: true,
        );

        if (albums.isNotEmpty) {
          final AssetPathEntity album = albums.first;
          final int count = await album.assetCountAsync;
          final List<AssetEntity> assets = await album.getAssetListRange(
            start: 0,
            end: count > 0 ? count : 100,
          );

          setState(() {
            _deviceAssets = assets;
            _isLoading = false;
          });
          return;
        }
      } else {
        _hasPermission = false;
      }
    } catch (e) {
      debugPrint('[PhotoManager load error]: $e');
    }

    // 기기 권한 거부 또는 사진이 없을 경우 백엔드 갤러리 로드
    await _loadBackendPhotos();
  }

  Future<void> _loadBackendPhotos() async {
    try {
      final items = await _apiService.fetchPhotos();
      setState(() {
        _backendPhotos = items;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = '사진 목록을 불러오지 못했습니다.\n($e)';
        _isLoading = false;
      });
    }
  }

  // 2. 기기 갤러리의 실제 사진들을 백엔드 AI 브레인으로 인덱싱 동기화
  Future<void> _syncDevicePhotosToBackend() async {
    if (_deviceAssets.isEmpty || _isSyncing) return;

    setState(() {
      _isSyncing = true;
      _syncedCount = 0;
      _totalToSync = _deviceAssets.length;
    });

    int successCount = 0;
    for (int i = 0; i < _deviceAssets.length; i++) {
      final asset = _deviceAssets[i];
      try {
        final Uint8List? bytes = await asset.originBytes;
        if (bytes != null) {
          final String name = asset.title ?? 'photo_${asset.id}.jpg';
          final String dateStr = asset.createDateTime.toIso8601String();

          await _apiService.uploadAndIndexPhoto(
            bytes: bytes,
            filename: name,
            clientDate: dateStr,
          );
          successCount++;
        }
      } catch (e) {
        debugPrint('[Sync error for photo $i]: $e');
      }

      if (mounted) {
        setState(() {
          _syncedCount = i + 1;
        });
      }
    }

    if (mounted) {
      setState(() {
        _isSyncing = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('🎉 $successCount장의 기기 사진이 AI 브레인에 인덱싱 완료되었습니다!'),
          backgroundColor: Colors.green.shade700,
        ),
      );
    }
  }

  void _openChatSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => ChatSheet(
        apiService: _apiService,
        onSearchCompleted: (result) {
          setState(() {
            _activeSearchResult = result;
          });
        },
      ),
    );
  }

  Future<void> _onDirectSearchSubmit(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return;

    FocusScope.of(context).unfocus();
    setState(() {
      _isLoading = true;
    });

    try {
      final res = await _apiService.searchPhotos(trimmed);
      setState(() {
        _isLoading = false;
      });

      if (res.status == 'need_clarification') {
        if (mounted) {
          _openChatSheet();
        }
      } else {
        setState(() {
          _activeSearchResult = res;
        });
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('검색 중 오류가 발생했습니다: $e')),
        );
      }
    }
  }

  void _showAssetDetailsDialog(AssetEntity asset) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        contentPadding: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        clipBehavior: Clip.antiAlias,
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AspectRatio(
              aspectRatio: 1.0,
              child: AssetEntityImage(
                asset,
                isOriginal: false,
                thumbnailSize: const ThumbnailSize.square(600),
                fit: BoxFit.cover,
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    asset.title ?? '기기 갤러리 사진',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '촬영 일자: ${asset.createDateTime.toString().substring(0, 19)}',
                    style: TextStyle(color: Colors.grey.shade700, fontSize: 13),
                  ),
                  Text(
                    '크기: ${asset.width} x ${asset.height}',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('닫기'),
          ),
        ],
      ),
    );
  }

  void _showPhotoDetailsDialog(PhotoItem photo) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        contentPadding: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        clipBehavior: Clip.antiAlias,
        content: SizedBox(
          width: 440,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Stack(
                  children: [
                    AspectRatio(
                      aspectRatio: 1.1,
                      child: Image.network(
                        ApiService.getImageUrl(photo.imageUrl),
                        fit: BoxFit.cover,
                        errorBuilder: (c, e, s) => Container(
                          color: Colors.grey.shade200,
                          child: const Icon(Icons.broken_image, size: 40),
                        ),
                      ),
                    ),
                    if (photo.photoCategory != null)
                      Positioned(
                        top: 12,
                        left: 12,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.75),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            photo.photoCategory!,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                    Positioned(
                      bottom: 8,
                      right: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.6),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          photo.id,
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 10,
                            fontFamily: 'monospace',
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.calendar_today, size: 14, color: Colors.blueGrey),
                              const SizedBox(width: 4),
                              Text(
                                photo.capturedDate ?? '촬영일자 미상 (EXIF 결측)',
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                              ),
                            ],
                          ),
                          if (photo.locationName != null)
                            Flexible(
                              child: Text(
                                '📍 ${photo.locationName}',
                                style: TextStyle(color: Colors.grey.shade700, fontSize: 12),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                      ),
                      const Divider(height: 20),
                      if (photo.peopleTraits != null && photo.peopleTraits!.isNotEmpty) ...[
                        const Text(
                          '👥 인물 외형 및 의상',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.black87),
                        ),
                        const SizedBox(height: 3),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            photo.peopleTraits!,
                            style: const TextStyle(fontSize: 12, color: Colors.black87, height: 1.4),
                          ),
                        ),
                        const SizedBox(height: 10),
                      ],
                      if (photo.backgroundDetails != null && photo.backgroundDetails!.isNotEmpty) ...[
                        const Text(
                          '🎨 미시적 배경 특징',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.black87),
                        ),
                        const SizedBox(height: 3),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            photo.backgroundDetails!,
                            style: const TextStyle(fontSize: 12, color: Colors.black87, height: 1.4),
                          ),
                        ),
                        const SizedBox(height: 10),
                      ],
                      if (photo.atmosphere != null && photo.atmosphere!.isNotEmpty) ...[
                        const Text(
                          '✨ 분위기 및 시간대',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.black87),
                        ),
                        const SizedBox(height: 3),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            photo.atmosphere!,
                            style: const TextStyle(fontSize: 12, color: Colors.black87, height: 1.4),
                          ),
                        ),
                        const SizedBox(height: 10),
                      ],
                      if (photo.mainObjects.isNotEmpty) ...[
                        const Text(
                          '🏷️ 주요 사물 (Objects)',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.black87),
                        ),
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: photo.mainObjects.map((obj) => Chip(
                            label: Text(obj, style: const TextStyle(fontSize: 11)),
                            padding: EdgeInsets.zero,
                            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            backgroundColor: const Color(0xFFEEF2FF),
                            labelStyle: const TextStyle(color: Color(0xFF3F51B5), fontWeight: FontWeight.w600),
                            side: BorderSide.none,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                          )).toList(),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('닫기'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: theme.colorScheme.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(Icons.photo_library_rounded, color: theme.colorScheme.primary, size: 20),
            ),
            const SizedBox(width: 10),
            const Text('기억 추적 스마트 갤러리'),
          ],
        ),
        actions: [
          // 기기 사진을 AI 브레인으로 인덱싱하는 동기화 버튼
          if (_deviceAssets.isNotEmpty)
            IconButton(
              icon: _isSyncing
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.cloud_upload_outlined),
              tooltip: '기기 사진 AI 인덱싱 동기화',
              onPressed: _isSyncing ? null : _syncDevicePhotosToBackend,
            ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: '새로고침',
            onPressed: _loadDeviceGalleryPhotos,
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(64),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Container(
              height: 48,
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.grey.shade300),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                children: [
                  Icon(Icons.search_rounded, color: theme.colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _searchController,
                      textInputAction: TextInputAction.search,
                      onSubmitted: _onDirectSearchSubmit,
                      decoration: const InputDecoration(
                        hintText: '구어체로 기억을 입력하세요 (예: 작년 이맘때 흰 벽)',
                        hintStyle: TextStyle(fontSize: 13, color: Colors.grey),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                  ),
                  InkWell(
                    onTap: _openChatSheet,
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.chat_bubble_outline_rounded, size: 12, color: theme.colorScheme.primary),
                          const SizedBox(width: 4),
                          Text(
                            '스무고개 AI',
                            style: TextStyle(
                              color: theme.colorScheme.primary,
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openChatSheet,
        backgroundColor: theme.colorScheme.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.chat_bubble_outline_rounded),
        label: const Text(
          '기억으로 찾기',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('갤러리 사진을 불러오는 중입니다...'),
          ],
        ),
      );
    }

    // 활성 검색 결과가 있는 경우 결과 카드 및 타임라인 뷰 표시
    if (_activeSearchResult != null) {
      return ResultView(
        response: _activeSearchResult!,
        onDismiss: () {
          setState(() {
            _activeSearchResult = null;
          });
        },
        onSelectDayPhoto: (photo) {
          _showPhotoDetailsDialog(photo);
        },
      );
    }

    // 1. 기기 실제 갤러리 사진이 로드된 경우 (GridView)
    if (_deviceAssets.isNotEmpty) {
      return RefreshIndicator(
        onRefresh: _loadDeviceGalleryPhotos,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_isSyncing)
              Container(
                color: Colors.amber.shade50,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Gemini AI 비전 인덱싱 동기화 중... ($_syncedCount / $_totalToSync장)',
                        style: TextStyle(fontSize: 12, color: Colors.amber.shade900, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 6),
              child: Row(
                children: [
                  Text(
                    '기기 실제 갤러리 (${_deviceAssets.length}장)',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: Colors.black87,
                    ),
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.green.shade50,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.green.shade200),
                    ),
                    child: Text(
                      '📱 실제 기기 앨범',
                      style: TextStyle(fontSize: 11, color: Colors.green.shade800, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: GridView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 3,
                  crossAxisSpacing: 6,
                  mainAxisSpacing: 6,
                  childAspectRatio: 1.0,
                ),
                itemCount: _deviceAssets.length,
                itemBuilder: (context, index) {
                  final asset = _deviceAssets[index];
                  return InkWell(
                    onTap: () => _showAssetDetailsDialog(asset),
                    borderRadius: BorderRadius.circular(8),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: AssetEntityImage(
                        asset,
                        isOriginal: false,
                        thumbnailSize: const ThumbnailSize.square(300),
                        fit: BoxFit.cover,
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      );
    }

    // 2. 에러가 발생한 경우
    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48, color: Colors.orange),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadDeviceGalleryPhotos,
                child: const Text('다시 시도'),
              ),
            ],
          ),
        ),
      );
    }

    // 3. 기기 권한이 거부되었거나 사진이 없는 경우
    if (!_hasPermission) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.photo_library_outlined, size: 64, color: Colors.indigo),
              const SizedBox(height: 16),
              const Text(
                '기기 갤러리 접근 권한이 필요합니다',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text(
                '에뮬레이터에 저장하신 100장의 실제 사진을\n조회하기 위해 권한을 허용해 주세요.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.black54, fontSize: 13),
              ),
              const SizedBox(height: 20),
              ElevatedButton.icon(
                onPressed: _loadDeviceGalleryPhotos,
                icon: const Icon(Icons.lock_open_rounded),
                label: const Text('권한 요청 및 갤러리 불러오기'),
              ),
            ],
          ),
        ),
      );
    }

    // 3. 백엔드 폴백 갤러리
    return RefreshIndicator(
      onRefresh: _loadDeviceGalleryPhotos,
      child: GridView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 3,
          crossAxisSpacing: 6,
          mainAxisSpacing: 6,
          childAspectRatio: 1.0,
        ),
        itemCount: _backendPhotos.length,
        itemBuilder: (context, index) {
          final photo = _backendPhotos[index];
          return InkWell(
            onTap: () => _showPhotoDetailsDialog(photo),
            borderRadius: BorderRadius.circular(8),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.network(
                ApiService.getImageUrl(photo.imageUrl),
                fit: BoxFit.cover,
              ),
            ),
          );
        },
      ),
    );
  }
}
