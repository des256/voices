import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'pages/home_page.dart';
import 'pages/login_page.dart';
import 'theme.dart';

void main() {
  runApp(VoicesApp(api: HttpVoicesApi(), picker: pickAudioFile));
}

Future<PickedAudio?> pickAudioFile() async {
  final result = await FilePicker.pickFiles(
    type: FileType.custom,
    allowedExtensions: const ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'oga', 'opus', 'flac', 'webm', 'mp4', 'wma', 'aiff'],
    withData: true,
  );
  if (result == null || result.files.isEmpty) return null;
  final file = result.files.single;
  final bytes = file.bytes;
  if (bytes == null) return null;
  return PickedAudio(file.name, bytes);
}

class VoicesApp extends StatelessWidget {
  const VoicesApp({super.key, required this.api, required this.picker, this.useGoogleFonts = true});

  final VoicesApi api;
  final AudioPicker picker;
  final bool useGoogleFonts;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Voices',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(useGoogleFonts: useGoogleFonts),
      home: Shell(api: api, picker: picker),
    );
  }
}

enum _Screen { loading, login, home }

class Shell extends StatefulWidget {
  const Shell({super.key, required this.api, required this.picker});

  final VoicesApi api;
  final AudioPicker picker;

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  _Screen _screen = _Screen.loading;

  @override
  void initState() {
    super.initState();
    _checkSession();
  }

  Future<void> _checkSession() async {
    bool ok = false;
    try {
      ok = await widget.api.hasSession();
    } catch (_) {
      ok = false;
    }
    if (mounted) setState(() => _screen = ok ? _Screen.home : _Screen.login);
  }

  Future<void> _login(String username, String password) async {
    await widget.api.login(username, password);
    if (mounted) setState(() => _screen = _Screen.home);
  }

  Future<void> _logout() async {
    try {
      await widget.api.logout();
    } catch (_) {}
    if (mounted) setState(() => _screen = _Screen.login);
  }

  @override
  Widget build(BuildContext context) {
    return switch (_screen) {
      _Screen.loading => const Scaffold(body: Center(child: CircularProgressIndicator())),
      _Screen.login => LoginPage(onLogin: _login),
      _Screen.home => HomePage(
          api: widget.api,
          picker: widget.picker,
          onSignOut: _logout,
          onSessionLost: () => setState(() => _screen = _Screen.login),
        ),
    };
  }
}
