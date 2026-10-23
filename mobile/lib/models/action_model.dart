class ActionModel {
  final String id;
  final String documentId;
  final String userId;
  final String actionType;
  final String title;
  final String? description;
  final DateTime? dueDate;
  final String status;
  final Map<String, dynamic> payload;
  final DateTime createdAt;

  ActionModel({
    required this.id,
    required this.documentId,
    required this.userId,
    required this.actionType,
    required this.title,
    this.description,
    this.dueDate,
    required this.status,
    this.payload = const {},
    required this.createdAt,
  });

  factory ActionModel.fromJson(Map<String, dynamic> json) {
    return ActionModel(
      id: json['id'] ?? '',
      documentId: json['documentId'] ?? json['document_id'] ?? '',
      userId: json['userId'] ?? json['user_id'] ?? '',
      actionType:
          json['actionType'] ?? json['action_type'] ?? 'RENEWAL_REMINDER',
      title: json['title'] ?? '',
      description: json['description'],
      dueDate: json['dueDate'] != null
          ? DateTime.tryParse(json['dueDate'])
          : (json['due_date'] != null
                ? DateTime.tryParse(json['due_date'])
                : null),
      status: json['status'] ?? 'PENDING',
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
      createdAt:
          DateTime.tryParse(json['createdAt'] ?? json['created_at'] ?? '') ??
          DateTime.now(),
    );
  }
}
