import 'dart:js_interop';

import 'package:web/web.dart' as web;

/// Offers [contents] as a file download named [fileName] without a server round-trip.
void downloadTextFile(String fileName, String contents) {
  final blob = web.Blob(
    [contents.toJS].toJS,
    web.BlobPropertyBag(type: 'text/markdown;charset=utf-8'),
  );
  final url = web.URL.createObjectURL(blob);
  final anchor = web.HTMLAnchorElement()
    ..href = url
    ..download = fileName
    ..style.display = 'none';
  web.document.body!.append(anchor);
  anchor.click();
  anchor.remove();
  web.URL.revokeObjectURL(url);
}
