import 'package:material_ui/material_ui.dart';
import '../models/photo_model.dart';
import '../services/api_service.dart';
import 'story_carousel.dart';

enum _RelatedTab { sameDay, similarMood }

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
  late _RelatedTab _relatedTab;
  bool _infoExpanded = false;
  final ScrollController _scrollController = ScrollController();

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _resetForResponse();
  }

  @override
  void didUpdateWidget(covariant ResultView oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 새 검색 결과가 들어오면 상태 초기화 (이전 사진이 남아있는 문제 방지)
    if (!identical(oldWidget.response, widget.response)) {
      _resetForResponse();
    }
  }

  void _resetForResponse() {
    _currentPhoto = widget.response.targetPhoto ??
        PhotoItem(id: 'none', filePath: '', imageUrl: '');
    _relatedTab = widget.response.dayStoryPhotos.isNotEmpty
        ? _RelatedTab.sameDay
        : _RelatedTab.similarMood;
    _infoExpanded = false;
  }

  bool get _isTargetPhoto => _currentPhoto.id == widget.response.targetPhoto?.id;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      controller: _scrollController,
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildStatusBar(),

          // 1. 내가 찾은 사진
          _buildSectionTitle(Icons.photo_rounded, _isTargetPhoto ? '내가 찾은 사진' : '선택한 사진',
              trailing: _isTargetPhoto
                  ? null
                  : TextButton(
                      onPressed: () => setState(() {
                        _currentPhoto = widget.response.targetPhoto ?? _currentPhoto;
                      }),
                      child: const Text('찾은 사진으로'),
                    )),
          _buildMainPhoto(),

          const SizedBox(height: 24),

          // 2. 같은 날 / 비슷한 분위기
          _buildRelatedSection(),

          const SizedBox(height: 16),

          // 3. 정보 보기 (펼침)
          _buildInfoSection(),
        ],
      ),
    );
  }

  Widget _buildStatusBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      child: Row(
        children: [
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.green.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green.shade300),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_circle_rounded, size: 16, color: Colors.green.shade700),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      '기억 복원 성공 (${(widget.response.confidenceScore * 100).toInt()}% 일치)',
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Colors.green.shade800,
                      ),
                    ),
                  ),
                ],
              ),
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
    );
  }

  Widget _buildSectionTitle(IconData icon, String title, {Widget? trailing}) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
      child: Row(
        children: [
          Icon(icon, size: 20, color: theme.colorScheme.primary),
          const SizedBox(width: 8),
          Text(
            title,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, letterSpacing: -0.3),
          ),
          const Spacer(),
          ?trailing,
        ],
      ),
    );
  }

  Widget _buildMainPhoto() {
    final photo = _currentPhoto;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0),
      child: Card(
        elevation: 6,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        clipBehavior: Clip.antiAlias,
        child: AspectRatio(
          aspectRatio: 1.0,
          child: photo.imageUrl.isEmpty
              ? _imagePlaceholder()
              : Image.network(
                  ApiService.getImageUrl(photo.imageUrl),
                  key: ValueKey(photo.id),
                  fit: BoxFit.cover,
                  errorBuilder: (ctx, err, stack) => _imagePlaceholder(),
                  loadingBuilder: (ctx, child, progress) {
                    if (progress == null) return child;
                    return Container(
                      color: Colors.grey.shade100,
                      child: const Center(child: CircularProgressIndicator()),
                    );
                  },
                ),
        ),
      ),
    );
  }

  Widget _imagePlaceholder() {
    return Container(
      color: Colors.grey.shade200,
      child: const Center(
        child: Icon(Icons.photo_size_select_actual_outlined, size: 48, color: Colors.grey),
      ),
    );
  }

  Widget _buildRelatedSection() {
    final dayPhotos = widget.response.dayStoryPhotos;
    final similarPhotos = widget.response.similarPhotos;
    if (dayPhotos.isEmpty && similarPhotos.isEmpty) {
      return const SizedBox.shrink();
    }

    final photos = _relatedTab == _RelatedTab.sameDay ? dayPhotos : similarPhotos;
    final dateText = widget.response.dayStoryDate ?? widget.response.targetPhoto?.capturedDate;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: SegmentedButton<_RelatedTab>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(
                value: _RelatedTab.sameDay,
                icon: const Icon(Icons.calendar_today_rounded, size: 16),
                label: Text('같은 날 (${dayPhotos.length})'),
                enabled: dayPhotos.isNotEmpty,
              ),
              ButtonSegment(
                value: _RelatedTab.similarMood,
                icon: const Icon(Icons.auto_awesome_rounded, size: 16),
                label: Text('비슷한 분위기 (${similarPhotos.length})'),
                enabled: similarPhotos.isNotEmpty,
              ),
            ],
            selected: {_relatedTab},
            onSelectionChanged: (s) => setState(() => _relatedTab = s.first),
          ),
        ),
        if (_relatedTab == _RelatedTab.sameDay && dateText != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Text(
              '$dateText 전후에 찍은 사진',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ),
        const SizedBox(height: 8),
        StoryCarousel(
          photos: photos,
          onPhotoSelected: (selected) {
            // 선택한 사진을 메인으로 올리고 맨 위로 스크롤 (정보는 '정보 보기'에서 확인)
            setState(() => _currentPhoto = selected);
            if (_scrollController.hasClients) {
              _scrollController.animateTo(0,
                  duration: const Duration(milliseconds: 300), curve: Curves.easeOutCubic);
            }
          },
        ),
      ],
    );
  }

  Widget _buildInfoSection() {
    final theme = Theme.of(context);
    final photo = _currentPhoto;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          OutlinedButton.icon(
            onPressed: () => setState(() => _infoExpanded = !_infoExpanded),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
            icon: AnimatedRotation(
              turns: _infoExpanded ? 0.5 : 0,
              duration: const Duration(milliseconds: 200),
              child: const Icon(Icons.expand_more_rounded),
            ),
            label: Text(_infoExpanded ? '정보 닫기' : '정보 보기'),
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOutCubic,
            alignment: Alignment.topCenter,
            child: !_infoExpanded
                ? const SizedBox(width: double.infinity)
                : Container(
                    margin: const EdgeInsets.only(top: 12),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // XAI 매칭 근거 태그 (찾은 사진일 때만 의미 있음)
                        if (_isTargetPhoto && widget.response.xaiTags.isNotEmpty) ...[
                          Text('이 사진을 찾은 이유',
                              style: TextStyle(
                                  fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey.shade800)),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: widget.response.xaiTags.map((tag) {
                              return Chip(
                                label: Text(tag,
                                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                                backgroundColor: theme.colorScheme.primary.withValues(alpha: 0.08),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(10),
                                  side: BorderSide(color: theme.colorScheme.primary.withValues(alpha: 0.25)),
                                ),
                                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                              );
                            }).toList(),
                          ),
                          const Divider(height: 24),
                        ],
                        _buildCueRow(Icons.calendar_month_outlined, '촬영일',
                            photo.capturedDate ?? '촬영일자 미상'),
                        const SizedBox(height: 6),
                        _buildCueRow(Icons.place_outlined, '장소', photo.locationName ?? '위치 정보 없음'),
                        if (_hasText(photo.photoCategory)) ...[
                          const SizedBox(height: 6),
                          _buildCueRow(Icons.category_outlined, '분류', photo.photoCategory!),
                        ],
                        if (_hasText(photo.peopleTraits)) ...[
                          const SizedBox(height: 6),
                          _buildCueRow(Icons.person_outline, '인물/의상', photo.peopleTraits!),
                        ],
                        if (_hasText(photo.backgroundDetails)) ...[
                          const SizedBox(height: 6),
                          _buildCueRow(Icons.wallpaper_outlined, '배경 단서', photo.backgroundDetails!),
                        ],
                        if (_hasText(photo.atmosphere)) ...[
                          const SizedBox(height: 6),
                          _buildCueRow(Icons.wb_sunny_outlined, '분위기/계절', photo.atmosphere!),
                        ],
                        if (photo.mainObjects.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          _buildCueRow(Icons.widgets_outlined, '주요 사물', photo.mainObjects.join(', ')),
                        ],
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  bool _hasText(String? s) => s != null && s.trim().isNotEmpty;

  Widget _buildCueRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 15, color: Colors.grey.shade600),
        const SizedBox(width: 6),
        Text(
          '$label: ',
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey.shade800),
        ),
        Expanded(
          child: Text(value, style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
        ),
      ],
    );
  }
}
