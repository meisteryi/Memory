import 'package:flutter/material.dart';
import '../models/photo_model.dart';
import '../services/api_service.dart';

class ChatSheet extends StatefulWidget {
  final ApiService apiService;
  final Function(SearchResponse) onSearchCompleted;

  const ChatSheet({
    super.key,
    required this.apiService,
    required this.onSearchCompleted,
  });

  @override
  State<ChatSheet> createState() => _ChatSheetState();
}

class _ChatSheetState extends State<ChatSheet> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessageModel> _messages = [];
  bool _isLoading = false;
  late final String _sessionId;

  final List<String> _quickSuggestions = [
    "작년 이맘때 친구들이랑 흰 벽 배경으로 찍은 사진",
    "주황색 벽 앞에서 패딩 입었던 거",
    "강릉에서 따뜻한 라떼 마신 겨울 카페",
    "제주도 푸른 바다에서 모자 쓰고 찍은 사진",
  ];

  @override
  void initState() {
    super.initState();
    _sessionId = 'session_${DateTime.now().millisecondsSinceEpoch}';
    _messages.add(
      ChatMessageModel(
        role: 'assistant',
        content: '안녕하세요! 찾고 계신 사진의 흐릿한 기억이라도 편하게 말씀해 주세요. (예: "작년 이맘때쯤 흰 벽에서 친구들이랑 찍은 거", "주황색 벽 패딩")',
      ),
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || _isLoading) return;

    _controller.clear();
    setState(() {
      _messages.add(ChatMessageModel(role: 'user', content: trimmed));
      _isLoading = true;
    });
    _scrollToBottom();

    try {
      final response = await widget.apiService.chatAndClarify(
        sessionId: _sessionId,
        message: trimmed,
        history: _messages,
      );

      if (!mounted) return;

      if (response.status == 'need_clarification' && response.clarificationQuestion != null) {
        setState(() {
          _messages.add(
            ChatMessageModel(
              role: 'assistant',
              content: response.clarificationQuestion!,
            ),
          );
          _isLoading = false;
        });
        _scrollToBottom();
      } else if (response.status == 'success' && response.targetPhoto != null) {
        setState(() {
          _messages.add(
            ChatMessageModel(
              role: 'assistant',
              content: '🎯 기억에 부합하는 최우선 사진을 찾았습니다! 그날의 타임라인 스토리와 함께 복원합니다.',
            ),
          );
          _isLoading = false;
        });
        _scrollToBottom();

        // 0.8초 후 바텀시트 닫고 메인 결과 화면으로 전환
        Future.delayed(const Duration(milliseconds: 800), () {
          if (mounted) {
            Navigator.of(context).pop();
            widget.onSearchCompleted(response);
          }
        });
      } else {
        setState(() {
          _messages.add(
            ChatMessageModel(
              role: 'assistant',
              content: '조건에 맞는 사진을 찾지 못했습니다. 다른 단서를 말씀해 주시겠어요?',
            ),
          );
          _isLoading = false;
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(
          ChatMessageModel(
            role: 'assistant',
            content: '오류가 발생했습니다: $e\n잠시 후 다시 시도해 주세요.',
          ),
        );
        _isLoading = false;
      });
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      height: MediaQuery.of(context).size.height * 0.75 + bottomInset,
      padding: EdgeInsets.only(bottom: bottomInset),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        children: [
          // 드래그 핸들 & 헤더
          Container(
            margin: const EdgeInsets.only(top: 12, bottom: 8),
            width: 44,
            height: 5,
            decoration: BoxDecoration(
              color: Colors.grey.shade300,
              borderRadius: BorderRadius.circular(2.5),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 6.0),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primary.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(Icons.psychology_alt_rounded, color: theme.colorScheme.primary, size: 22),
                ),
                const SizedBox(width: 10),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '기억 복원 스무고개 에이전트',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    Text(
                      '모호한 기억 표현을 능동적으로 좁혀 찾아드립니다',
                      style: TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                  ],
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
          const Divider(height: 1),

          // 추천 빠른 입력 칩
          if (_messages.length <= 2)
            Container(
              height: 44,
              margin: const EdgeInsets.symmetric(vertical: 4),
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _quickSuggestions.length,
                itemBuilder: (context, index) {
                  final text = _quickSuggestions[index];
                  return Padding(
                    padding: const EdgeInsets.only(right: 8.0),
                    child: ActionChip(
                      label: Text(text, style: const TextStyle(fontSize: 12)),
                      backgroundColor: Colors.grey.shade100,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      onPressed: () => _sendMessage(text),
                    ),
                  );
                },
              ),
            ),

          // 대화 말풍선 리스트
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                final isUser = msg.role == 'user';
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 5),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.78,
                    ),
                    decoration: BoxDecoration(
                      color: isUser ? theme.colorScheme.primary : Colors.grey.shade100,
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(16),
                        topRight: const Radius.circular(16),
                        bottomLeft: isUser ? const Radius.circular(16) : const Radius.circular(4),
                        bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(16),
                      ),
                    ),
                    child: Text(
                      msg.content,
                      style: TextStyle(
                        color: isUser ? Colors.white : Colors.black87,
                        fontSize: 14,
                        height: 1.35,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),

          if (_isLoading)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
              child: Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '인지 기억 및 비전 단서 추적 중...',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600, fontStyle: FontStyle.italic),
                  ),
                ],
              ),
            ),

          // 하단 텍스트 입력창
          Container(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 4, offset: const Offset(0, -2)),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    textInputAction: TextInputAction.send,
                    onSubmitted: _sendMessage,
                    decoration: InputDecoration(
                      hintText: '기억나는 옷차림, 배경, 시점을 입력하세요...',
                      hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 13),
                      filled: true,
                      fillColor: Colors.grey.shade100,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _isLoading ? null : () => _sendMessage(_controller.text),
                  icon: const Icon(Icons.arrow_upward_rounded),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
