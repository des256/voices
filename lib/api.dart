import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.status, this.message);
  final int status;
  final String message;

  @override
  String toString() => message;
}

class JobStatus {
  JobStatus({
    required this.id,
    required this.fileName,
    required this.status,
    required this.progress,
    required this.stage,
    this.error,
  });

  factory JobStatus.fromJson(Map<String, dynamic> json) => JobStatus(
        id: json['id'] as String,
        fileName: json['file_name'] as String? ?? '',
        status: json['status'] as String,
        progress: (json['progress'] as num? ?? 0).toDouble(),
        stage: json['stage'] as String? ?? '',
        error: json['error'] as String?,
      );

  final String id;
  final String fileName;
  final String status;
  final double progress;
  final String stage;
  final String? error;

  bool get isDone => status == 'done';
  bool get isError => status == 'error';
}

/// The backend contract. [HttpVoicesApi] talks to `/api` on the same origin.
abstract class VoicesApi {
  Future<bool> hasSession();
  Future<void> login(String username, String password);
  Future<void> logout();
  Future<JobStatus> upload(String fileName, Uint8List bytes);

  /// Returns null when the job is unknown to the server.
  Future<JobStatus?> job(String id);
  Future<String> report(String id);
}

class HttpVoicesApi implements VoicesApi {
  HttpVoicesApi({http.Client? client, Uri? base})
      : _client = client ?? http.Client(),
        _base = base ?? Uri.base;

  final http.Client _client;
  final Uri _base;

  Uri _url(String path) => _base.resolve(path);

  String _detail(http.Response response) {
    try {
      final body = jsonDecode(response.body);
      if (body is Map && body['detail'] is String) return body['detail'] as String;
    } catch (_) {}
    return 'Request failed (${response.statusCode})';
  }

  void _check(http.Response response) {
    if (response.statusCode >= 400) {
      throw ApiException(response.statusCode, _detail(response));
    }
  }

  @override
  Future<bool> hasSession() async {
    final response = await _client.get(_url('/api/session'));
    if (response.statusCode == 401) return false;
    _check(response);
    return true;
  }

  @override
  Future<void> login(String username, String password) async {
    final response = await _client.post(
      _url('/api/login'),
      headers: {'content-type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    _check(response);
  }

  @override
  Future<void> logout() async {
    _check(await _client.post(_url('/api/logout')));
  }

  @override
  Future<JobStatus> upload(String fileName, Uint8List bytes) async {
    final request = http.MultipartRequest('POST', _url('/api/jobs'))
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: fileName));
    final response = await http.Response.fromStream(await _client.send(request));
    _check(response);
    return JobStatus.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  @override
  Future<JobStatus?> job(String id) async {
    final response = await _client.get(_url('/api/jobs/$id'));
    if (response.statusCode == 404) return null;
    _check(response);
    return JobStatus.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  @override
  Future<String> report(String id) async {
    final response = await _client.get(_url('/api/jobs/$id/report'));
    _check(response);
    return utf8.decode(response.bodyBytes);
  }
}
