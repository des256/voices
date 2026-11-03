import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

class ReportView extends StatelessWidget {
  const ReportView({
    super.key,
    required this.fileName,
    required this.markdown,
    required this.onDownload,
    required this.onNewAnalysis,
  });

  final String fileName;
  final String markdown;
  final VoidCallback onDownload;
  final VoidCallback onNewAnalysis;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = theme.textTheme;
    final sheet = MarkdownStyleSheet.fromTheme(theme).copyWith(
      h1: text.displayMedium,
      h2: text.displaySmall?.copyWith(height: 2),
      h3: text.headlineMedium?.copyWith(height: 2),
      p: text.bodyLarge?.copyWith(height: 1.5),
      listBullet: text.bodyLarge,
      tableHead: text.bodyMedium?.copyWith(fontWeight: FontWeight.w700),
      tableBody: text.bodyMedium,
      tableBorder: TableBorder.all(color: Colors.white24),
      tableCellsPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      tableColumnWidth: const FlexColumnWidth(),
      blockquoteDecoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(4)),
      horizontalRuleDecoration: const BoxDecoration(border: Border(top: BorderSide(color: Colors.white24))),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text('Report for $fileName', style: text.headlineMedium, overflow: TextOverflow.ellipsis),
            ),
            const SizedBox(width: 12),
            FilledButton.icon(
              key: const Key('download'),
              onPressed: onDownload,
              icon: const Icon(Icons.download),
              label: const Text('Download report'),
            ),
            const SizedBox(width: 8),
            TextButton.icon(
              onPressed: onNewAnalysis,
              icon: const Icon(Icons.add),
              label: const Text('New analysis'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Expanded(
          child: Card(
            clipBehavior: Clip.antiAlias,
            child: Markdown(
              data: markdown,
              selectable: true,
              styleSheet: sheet,
              padding: const EdgeInsets.all(28),
            ),
          ),
        ),
      ],
    );
  }
}
