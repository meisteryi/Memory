class PhotoItem {
  final String id;
  final String filePath;
  final String imageUrl;
  final String? photoCategory;
  final String? capturedDate;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final String? locationName;
  final String? peopleTraits;
  final String? atmosphere;
  final String? backgroundDetails;
  final List<String> mainObjects;

  PhotoItem({
    required this.id,
    required this.filePath,
    required this.imageUrl,
    this.photoCategory,
    this.capturedDate,
    this.gpsLatitude,
    this.gpsLongitude,
    this.locationName,
    this.peopleTraits,
    this.atmosphere,
    this.backgroundDetails,
    this.mainObjects = const [],
  });

  factory PhotoItem.fromJson(Map<String, dynamic> json) {
    return PhotoItem(
      id: json['id'] ?? '',
      filePath: json['file_path'] ?? '',
      imageUrl: json['image_url'] ?? '',
      photoCategory: json['photo_category'],
      capturedDate: json['captured_date'],
      gpsLatitude: json['gps_latitude'] != null ? (json['gps_latitude'] as num).toDouble() : null,
      gpsLongitude: json['gps_longitude'] != null ? (json['gps_longitude'] as num).toDouble() : null,
      locationName: json['location_name'],
      peopleTraits: json['people_traits'],
      atmosphere: json['atmosphere'],
      backgroundDetails: json['background_details'],
      mainObjects: json['main_objects'] != null
          ? List<String>.from(json['main_objects'])
          : const [],
    );
  }
}

class ParsedUserQuery {
  final String? targetCategory;
  final List<String> locationCandidates;
  final String? startDate;
  final String? endDate;
  final String semanticQuery;
  final double confidenceScore;
  final String? clarificationQuestion;

  ParsedUserQuery({
    this.targetCategory,
    this.locationCandidates = const [],
    this.startDate,
    this.endDate,
    required this.semanticQuery,
    this.confidenceScore = 0.8,
    this.clarificationQuestion,
  });

  factory ParsedUserQuery.fromJson(Map<String, dynamic> json) {
    return ParsedUserQuery(
      targetCategory: json['target_category'],
      locationCandidates: json['location_candidates'] != null
          ? List<String>.from(json['location_candidates'])
          : const [],
      startDate: json['start_date'],
      endDate: json['end_date'],
      semanticQuery: json['semantic_query'] ?? '',
      confidenceScore: json['confidence_score'] != null
          ? (json['confidence_score'] as num).toDouble()
          : 0.8,
      clarificationQuestion: json['clarification_question'],
    );
  }
}

class SearchResponse {
  final String status;
  final double confidenceScore;
  final String? clarificationQuestion;
  final PhotoItem? targetPhoto;
  final List<String> xaiTags;
  final List<PhotoItem> dayStoryPhotos;
  final String? dayStoryDate;
  final ParsedUserQuery? parsedQuery;
  final bool fallbackUsed;

  SearchResponse({
    required this.status,
    required this.confidenceScore,
    this.clarificationQuestion,
    this.targetPhoto,
    this.xaiTags = const [],
    this.dayStoryPhotos = const [],
    this.dayStoryDate,
    this.parsedQuery,
    this.fallbackUsed = false,
  });

  factory SearchResponse.fromJson(Map<String, dynamic> json) {
    return SearchResponse(
      status: json['status'] ?? 'success',
      confidenceScore: json['confidence_score'] != null
          ? (json['confidence_score'] as num).toDouble()
          : 0.8,
      clarificationQuestion: json['clarification_question'],
      targetPhoto: json['target_photo'] != null
          ? PhotoItem.fromJson(json['target_photo'])
          : null,
      xaiTags: json['xai_tags'] != null ? List<String>.from(json['xai_tags']) : [],
      dayStoryPhotos: json['day_story_photos'] != null
          ? (json['day_story_photos'] as List)
              .map((e) => PhotoItem.fromJson(e))
              .toList()
          : [],
      dayStoryDate: json['day_story_date'],
      parsedQuery: json['parsed_query'] != null
          ? ParsedUserQuery.fromJson(json['parsed_query'])
          : null,
      fallbackUsed: json['fallback_used'] ?? false,
    );
  }
}

class ChatMessageModel {
  final String role; // 'user' | 'assistant'
  final String content;
  final DateTime timestamp;

  ChatMessageModel({
    required this.role,
    required this.content,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  Map<String, dynamic> toJson() => {
        'role': role,
        'content': content,
      };
}

