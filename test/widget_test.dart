import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voices/api.dart';
import 'package:voices/main.dart';
import 'package:voices/pages/home_page.dart';

class FakeApi implements VoicesApi {
  bool session = false;
  int polls = 0;
  String? uploadedName;

  @override
  Future<bool> hasSession() async => session;

  @override
  Future<void> login(String username, String password) async {
    if (password != 'pw') throw ApiException(401, 'Wrong username or password');
    session = true;
  }

  @override
  Future<void> logout() async => session = false;

  @override
  Future<JobStatus> upload(String fileName, Uint8List bytes) async {
    uploadedName = fileName;
    return JobStatus(id: 'job1', fileName: fileName, status: 'queued', progress: 0, stage: 'Queued');
  }

  @override
  Future<JobStatus?> job(String id) async {
    polls++;
    return polls < 2
        ? JobStatus(id: id, fileName: uploadedName ?? '', status: 'running', progress: 0.5, stage: 'Transcribing')
        : JobStatus(id: id, fileName: uploadedName ?? '', status: 'done', progress: 1, stage: 'Done');
  }

  @override
  Future<String> report(String id) async => '# Voice Analysis Report\n\nSpeaking rate 140 wpm.';
}

Future<PickedAudio?> fakePicker() async => PickedAudio('student.mp3', Uint8List.fromList([1, 2, 3]));

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('signs in, uploads a recording, shows progress, then the report with a download button', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(VoicesApp(api: api, picker: fakePicker, useGoogleFonts: false));
    await tester.pumpAndSettle();

    expect(find.text('Sign in'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('username')), 'coach');
    await tester.enterText(find.byKey(const Key('password')), 'wrong');
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Wrong username or password'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('password')), 'pw');
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Analyze a recording'), findsOneWidget);

    await tester.tap(find.byKey(const Key('choose')));
    await tester.pumpAndSettle();
    expect(find.textContaining('student.mp3'), findsOneWidget);

    await tester.tap(find.byKey(const Key('analyze')));
    await tester.pumpAndSettle();
    expect(api.uploadedName, 'student.mp3');
    expect(find.text('Analyzing student.mp3'), findsOneWidget);

    await tester.pump(pollInterval);
    await tester.pumpAndSettle();
    expect(find.text('50%  ·  Transcribing'), findsOneWidget);

    await tester.pump(pollInterval);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('download')), findsOneWidget);
    expect(find.text('Voice Analysis Report'), findsOneWidget);
    expect(find.textContaining('Speaking rate 140 wpm'), findsOneWidget);

    await tester.tap(find.text('New analysis'));
    await tester.pumpAndSettle();
    expect(find.text('Analyze a recording'), findsOneWidget);
  });

  testWidgets('resumes a saved job after reload and shows its finished report', (tester) async {
    SharedPreferences.setMockInitialValues({'voices.currentJob': 'job1'});
    final api = FakeApi()
      ..session = true
      ..polls = 5;
    await tester.pumpWidget(VoicesApp(api: api, picker: fakePicker, useGoogleFonts: false));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('download')), findsOneWidget);
  });
}
