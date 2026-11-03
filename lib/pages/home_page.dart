import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api.dart';
import '../download.dart';
import 'report_view.dart';

class PickedAudio {
  PickedAudio(this.name, this.bytes);
  final String name;
  final Uint8List bytes;
}

typedef AudioPicker = Future<PickedAudio?> Function();

enum Phase { idle, uploading, running, report }

const _jobKey = 'voices.currentJob';
const pollInterval = Duration(milliseconds: 1500);

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.api, required this.picker, required this.onSignOut, required this.onSessionLost});

  final VoicesApi api;
  final AudioPicker picker;
  final Future<void> Function() onSignOut;
  final VoidCallback onSessionLost;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  Phase _phase = Phase.idle;
  PickedAudio? _picked;
  JobStatus? _job;
  String? _report;
  String? _error;
  Timer? _timer;
  bool _polling = false;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final id = prefs.getString(_jobKey);
    if (id == null) return;
    try {
      final job = await widget.api.job(id);
      if (!mounted) return;
      if (job == null) {
        await prefs.remove(_jobKey);
      } else if (job.isDone) {
        await _showReport(job);
      } else if (job.isError) {
        await prefs.remove(_jobKey);
        setState(() => _error = job.error ?? 'The analysis failed.');
      } else {
        setState(() {
          _job = job;
          _phase = Phase.running;
        });
        _startPolling();
      }
    } on ApiException catch (e) {
      _handleApiError(e);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  void _handleApiError(ApiException e) {
    if (e.status == 401) {
      widget.onSessionLost();
      return;
    }
    if (mounted) setState(() => _error = e.message);
  }

  Future<void> _choose() async {
    final picked = await widget.picker();
    if (picked == null || !mounted) return;
    setState(() {
      _picked = picked;
      _error = null;
    });
  }

  Future<void> _analyze() async {
    final picked = _picked;
    if (picked == null) return;
    setState(() {
      _phase = Phase.uploading;
      _error = null;
    });
    try {
      final job = await widget.api.upload(picked.name, picked.bytes);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_jobKey, job.id);
      if (!mounted) return;
      setState(() {
        _job = job;
        _phase = Phase.running;
      });
      _startPolling();
    } on ApiException catch (e) {
      if (mounted) setState(() => _phase = Phase.idle);
      _handleApiError(e);
    } catch (e) {
      if (mounted) {
        setState(() {
          _phase = Phase.idle;
          _error = e.toString();
        });
      }
    }
  }

  void _startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(pollInterval, (_) => _poll());
  }

  Future<void> _poll() async {
    final current = _job;
    if (current == null || _polling) return;
    _polling = true;
    try {
      final job = await widget.api.job(current.id);
      if (!mounted) return;
      if (job == null) {
        _timer?.cancel();
        await _clearSaved();
        setState(() {
          _phase = Phase.idle;
          _error = 'The server no longer knows this analysis. Please upload again.';
        });
      } else if (job.isDone) {
        _timer?.cancel();
        await _showReport(job);
      } else if (job.isError) {
        _timer?.cancel();
        await _clearSaved();
        setState(() {
          _phase = Phase.idle;
          _job = null;
          _error = job.error ?? 'The analysis failed.';
        });
      } else {
        setState(() => _job = job);
      }
    } on ApiException catch (e) {
      _timer?.cancel();
      _handleApiError(e);
    } catch (_) {
      // transient network problem: keep polling
    } finally {
      _polling = false;
    }
  }

  Future<void> _showReport(JobStatus job) async {
    final report = await widget.api.report(job.id);
    if (!mounted) return;
    setState(() {
      _job = job;
      _report = report;
      _phase = Phase.report;
      _error = null;
    });
  }

  Future<void> _clearSaved() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_jobKey);
  }

  Future<void> _reset() async {
    _timer?.cancel();
    await _clearSaved();
    if (!mounted) return;
    setState(() {
      _phase = Phase.idle;
      _picked = null;
      _job = null;
      _report = null;
      _error = null;
    });
  }

  void _download() {
    final report = _report;
    final job = _job;
    if (report == null || job == null) return;
    final stem = job.fileName.replaceAll(RegExp(r'\.[^.]+$'), '').replaceAll(RegExp(r'[^A-Za-z0-9._-]+'), '-');
    downloadTextFile('voices-report-${stem.isEmpty ? 'recording' : stem}.md', report);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Voices'),
        actions: [
          TextButton.icon(
            onPressed: widget.onSignOut,
            icon: const Icon(Icons.logout, size: 18),
            label: const Text('Sign out'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
            child: switch (_phase) {
              Phase.idle => _buildIdle(context),
              Phase.uploading => _buildProgress(context, uploading: true),
              Phase.running => _buildProgress(context, uploading: false),
              Phase.report => ReportView(
                  fileName: _job?.fileName ?? '',
                  markdown: _report ?? '',
                  onDownload: _download,
                  onNewAnalysis: _reset,
                ),
            },
          ),
        ),
      ),
    );
  }

  Widget _buildIdle(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final picked = _picked;
    return SingleChildScrollView(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Analyze a recording', style: text.displaySmall),
              const SizedBox(height: 8),
              Text(
                'Upload a recording of a student speaking. You get a report with the transcript, speaking pace, '
                'pauses, filler words, pitch and loudness variation, voice clarity, emotional expression and the tone of the content.',
                style: text.bodyLarge,
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 16,
                runSpacing: 12,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  OutlinedButton.icon(
                    key: const Key('choose'),
                    onPressed: _choose,
                    icon: const Icon(Icons.upload_file),
                    label: Text(picked == null ? 'Choose audio file' : 'Choose another file'),
                  ),
                  if (picked != null)
                    Text('${picked.name}  ·  ${(picked.bytes.length / (1024 * 1024)).toStringAsFixed(1)} MB', style: text.bodyLarge),
                ],
              ),
              const SizedBox(height: 8),
              Text('MP3, WAV, M4A, AAC, OGG, FLAC or WebM, up to 60 minutes.', style: text.bodyMedium?.copyWith(color: Colors.white60)),
              const SizedBox(height: 24),
              FilledButton.icon(
                key: const Key('analyze'),
                onPressed: picked == null ? null : _analyze,
                icon: const Icon(Icons.graphic_eq),
                label: const Text('Analyze'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildProgress(BuildContext context, {required bool uploading}) {
    final text = Theme.of(context).textTheme;
    final job = _job;
    final progress = uploading ? null : job?.progress;
    final stage = uploading ? 'Uploading' : (job?.stage ?? 'Queued');
    final name = uploading ? (_picked?.name ?? '') : (job?.fileName ?? '');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Analyzing $name', style: text.displaySmall),
            const SizedBox(height: 20),
            LinearProgressIndicator(value: progress, minHeight: 10, borderRadius: BorderRadius.circular(5)),
            const SizedBox(height: 12),
            Text(
              progress == null ? '$stage…' : '${(progress * 100).round()}%  ·  $stage',
              key: const Key('stage'),
              style: text.headlineMedium,
            ),
            const SizedBox(height: 16),
            Text(
              'Transcription and emotion models run on a small server, so a long recording can take several minutes. '
              'You can keep this tab open or come back later; the result is kept for you.',
              style: text.bodyMedium?.copyWith(color: Colors.white60),
            ),
          ],
        ),
      ),
    );
  }
}
