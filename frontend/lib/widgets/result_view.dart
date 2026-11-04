import 'package:flutter/material.dart';
import '../models/photo_model.dart';
import '../services/api_service.dart';
import 'story_carousel.dart';

class ResultView extends StatefulWidget {
  final SearchResponse response;
  final VoidCallback onDismiss;
  final Function(PhotoItem) onSelectDayPhoto;

  const ResultView({
    super.key,
    required this.response,
    required this.onDismiss,
    required this.onSelectDayPhoto,
  });

  @override
  State<ResultView> createState() => _ResultViewState();
}

class _ResultViewState extends State<ResultView> {
  late PhotoItem _currentPhoto;

  @override
  void initState() {
    super.initState();
    _currentPhoto = widget.response.targetPhoto ??
        PhotoItem(id: 'none', filePath: '', imageUrl: '');
  }

  @override
  Widget build(BuildContext context) {
    final photo = _currentPhoto;
    final theme = Theme.of(context);

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 상단 상태 바 & 닫기 버튼
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.green.shade300),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.check_circle_rounded, size: 16, color: Colors.green.shade700),
                      const SizedBox(width: 4),
                      Text(
                        '기억 복원 성공 (${(widget.response.confidenceScore * 100).toInt()}% 일치)',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: Colors.green.shade800,
                        ),
                      ),
                    ],
                  ),
                ),
                if (widget.response.fallbackUsed) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '소프트 벡터 검색',
                      style: TextStyle(fontSize: 11, color: Colors.orange.shade800),
                    ),
                  ),
                ],
                const Spacer(),
                IconButton(
                  onPressed: widget.onDismiss,
                  icon: const Icon(Icons.close_rounded),
                  tooltip: '전체 갤러리로 돌아가기',
                ),
              ],
            ),
          ),

          // 메인 타겟 사진 하이라이트 카드
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: Card(
              elevation: 6,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
              clipBehavior: Clip.antiAlias,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  AspectRatio(
                    aspectRatio: 1.0,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        Image.network(
                          ApiService.getImageUrl(photo.imageUrl),
                          fit: BoxFit.cover,
                          errorBuilder: (ctx, err, stack) => Container(
                            color: Colors.grey.shade200,
                            child: const Center(
                              child: Icon(Icons.photo_size_select_actual_outlined, size: 48, color: Colors.grey),
                            ),
                          ),
                          loadingBuilder: (ctx, child, progress) {
                            if (progress == null) return child;
                            return Container(
                              color: Colors.grey.shade100,
                              child: const Center(child: CircularProgressIndicator()),
                            );
                          },
                        ),
                        // 상단 배지
                        Positioned(
                          top: 12,
                          left: 12,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.65),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Text(
                              '🎯 최우선 매칭 기억',
                              style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // 카드 하단 메타데이터 및 설명
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // XAI 매칭 근거 태그 칩스
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: widget.response.xaiTags.map((tag) {
                            return Chip(
                              label: Text(tag, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                              backgroundColor: theme.colorScheme.primary.withValues(alpha: 0.08),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                                side: BorderSide(color: theme.colorScheme.primary.withValues(alpha: 0.25)),
                              ),
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 12),

                        // 시공간 정보
                        Row(
                          children: [
                            Icon(Icons.calendar_month_outlined, size: 16, color: Colors.grey.shade700),
                            const SizedBox(width: 6),
                            Text(
                              photo.capturedDate ?? '촬영일자 미상 (EXIF 결측 방어)',
                              style: TextStyle(
                                fontSize: 13,
                                color: photo.capturedDate != null ? Colors.black87 : Colors.grey.shade600,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            if (photo.locationName != null) ...[
                              const SizedBox(width: 12),
                              Icon(Icons.place_outlined, size: 16, color: Colors.red.shade400),
                              const SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  photo.locationName!,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                ),
                              ),
                            ],
                          ],
                        ),

                        const Divider(height: 24),

                        // 미시적 시각 단서 상세
                        if (photo.peopleTraits != null && photo.peopleTraits!.isNotEmpty) ...[
                          _buildCueRow(Icons.person_outline, '인물/의상', photo.peopleTraits!),
                          const SizedBox(height: 6),
                        ],
                        if (photo.backgroundDetails != null && photo.backgroundDetails!.isNotEmpty) ...[
                          _buildCueRow(Icons.wallpaper_outlined, '배경 단서', photo.backgroundDetails!),
                          const SizedBox(height: 6),
                        ],
                        if (photo.atmosphere != null && photo.atmosphere!.isNotEmpty) ...[
                          _buildCueRow(Icons.wb_sunny_outlined, '분위기/계절', photo.atmosphere!),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // 당일 맥락 확장 스토리 슬라이더
          if (widget.response.dayStoryPhotos.isNotEmpty)
            StoryCarousel(
              dateText: widget.response.dayStoryDate ?? _currentPhoto.capturedDate ?? '',
              photos: widget.response.dayStoryPhotos,
              onPhotoSelected: (selected) {
                setState(() {
                  _currentPhoto = selected;
                });
                widget.onSelectDayPhoto(selected);
              },
            ),
        ],
      ),
    );
  }

  Widget _buildCueRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 15, color: Colors.grey.shade600),
        const SizedBox(width: 6),
        Text(
          '$label: ',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.bold,
            color: Colors.grey.shade800,
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey.shade700,
            ),
          ),
        ),
      ],
    );
  }
}
