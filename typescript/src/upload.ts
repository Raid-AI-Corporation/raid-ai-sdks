/**
 * A file to upload. `data` accepts the common byte containers plus `Blob`/`File`
 * (browser) so the same call works in Node 18+ and the browser.
 */
export interface FileInput {
  data: Uint8Array | ArrayBuffer | Blob;
  /** File name sent in the multipart part (e.g. `"photo.jpg"`). */
  fileName: string;
  /** MIME type (e.g. `"image/jpeg"`). Defaults to `application/octet-stream`. */
  contentType?: string;
}

/** Append a `FileInput` to a `FormData` under `field`, wrapping raw bytes in a `Blob`. */
export function appendFile(form: FormData, field: string, file: FileInput): void {
  const type = file.contentType ?? "application/octet-stream";
  const blob = file.data instanceof Blob ? file.data : new Blob([toBlobPart(file.data)], { type });
  form.append(field, blob, file.fileName);
}

function toBlobPart(data: Uint8Array | ArrayBuffer): BlobPart {
  // Both are valid BlobParts; the cast narrows the union for TS's BlobPart type.
  return data as BlobPart;
}
