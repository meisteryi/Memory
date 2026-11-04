import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/photo_model.dart';

class ApiService {
  // 기본 로컬 서버 URL (플랫폼별 주소 대응)
  static String get baseUrl {
    if (kIsWeb) return 'http://127.0.0.1:8000';
    // 안드로이드 에뮬레이터의 경우 10.0.2.2 권장되나 기본은 로컬호스트
    return 'http://127.0.0.1:8000';
  }

  static String getImageUrl(String relativePath) {
    if (relativePath.startsWith('http://') || relativePath.startsWith('https://')) {
      return relativePath;
    }
    final cleanPath = relativePath.startsWith('/') ? relativePath : '/$relativePath';
    return '$baseUrl$cleanPath';
  }

  // 1. 전체 사진 목록 조회 (갤러리 3열 그리드용)
  Future<List<PhotoItem>> fetchPhotos() async {
    try {
      final uri = Uri.parse('$baseUrl/api/photos');
      final res = await http.get(uri).timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        final List data = jsonDecode(utf8.decode(res.bodyBytes));
        return data.map((json) => PhotoItem.fromJson(json)).toList();
      } else {
        throw Exception('서버 응답 오류: ${res.statusCode}');
      }
    } catch (e) {
      debugPrint('[ApiService.fetchPhotos Error]: $e');
      rethrow;
    }
  }

  // 2. 단일 자연어 검색
  Future<SearchResponse> searchPhotos(String query) async {
    try {
      final uri = Uri.parse('$baseUrl/api/search');
      final res = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'query': query}),
      ).timeout(const Duration(seconds: 20));

      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        return SearchResponse.fromJson(data);
      } else {
        throw Exception('검색 실패 (${res.statusCode}): ${utf8.decode(res.bodyBytes)}');
      }
    } catch (e) {
      debugPrint('[ApiService.searchPhotos Error]: $e');
      rethrow;
    }
  }

  // 3. 스무고개 멀티턴 대화형 검색
  Future<SearchResponse> chatAndClarify({
    required String sessionId,
    required String message,
    required List<ChatMessageModel> history,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/chat');
      final body = {
        'session_id': sessionId,
        'message': message,
        'history': history.map((m) => m.toJson()).toList(),
      };

      final res = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 25));

      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        return SearchResponse.fromJson(data);
      } else {
        throw Exception('대화 실패 (${res.statusCode}): ${utf8.decode(res.bodyBytes)}');
      }
    } catch (e) {
      debugPrint('[ApiService.chatAndClarify Error]: $e');
      rethrow;
    }
  }

  // 4. 로컬 기기 사진을 백엔드에 업로드 및 AI 인덱싱
  Future<PhotoItem> uploadAndIndexPhoto({
    required Uint8List bytes,
    required String filename,
    String? clientDate,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/upload_and_index');
      final request = http.MultipartRequest('POST', uri);

      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: filename,
        ),
      );

      if (clientDate != null) {
        request.fields['client_date'] = clientDate;
      }

      final streamedResponse = await request.send().timeout(const Duration(seconds: 30));
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        return PhotoItem.fromJson(data);
      } else {
        throw Exception('업로드 실패 (${response.statusCode}): ${response.body}');
      }
    } catch (e) {
      debugPrint('[ApiService.uploadAndIndexPhoto Error]: $e');
      rethrow;
    }
  }
}

