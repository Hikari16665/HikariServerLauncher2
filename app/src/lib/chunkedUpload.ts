import { invoke } from "@tauri-apps/api/core";

const CHUNK_SIZE = 4 * 1024 * 1024;

export type UploadResponse = {
  status: number;
  body: string;
  error: string | null;
};

type UploadOptions = {
  url: string;
  file: File;
  token: string;
  signal?: AbortSignal;
  onProgress?: (progress: number) => void;
};

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const step = 32 * 1024;
  for (let offset = 0; offset < bytes.length; offset += step) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + step));
  }
  return btoa(binary);
}

function throwIfAborted(signal?: AbortSignal) {
  if (signal?.aborted) throw new DOMException("上传已取消", "AbortError");
}

async function finishUpload(uploadId: string, signal?: AbortSignal) {
  if (!signal) {
    return invoke<UploadResponse>("proxy_upload_finish", {
      req: { upload_id: uploadId },
    });
  }
  throwIfAborted(signal);
  return await new Promise<UploadResponse>((resolve, reject) => {
    const abort = () => {
      void invoke("proxy_upload_abort", {
        req: { upload_id: uploadId },
      });
      reject(new DOMException("上传已取消", "AbortError"));
    };
    signal.addEventListener("abort", abort, { once: true });
    invoke<UploadResponse>("proxy_upload_finish", {
      req: { upload_id: uploadId },
    }).then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

export async function uploadFileInChunks({
  url,
  file,
  token,
  signal,
  onProgress,
}: UploadOptions): Promise<UploadResponse> {
  throwIfAborted(signal);
  const { upload_id: uploadId } = await invoke<{ upload_id: string }>(
    "proxy_upload_begin",
    {
      req: {
        url,
        file_name: file.name,
        file_size: file.size,
        token,
      },
    },
  );

  try {
    if (file.size === 0) onProgress?.(90);
    for (let offset = 0; offset < file.size; offset += CHUNK_SIZE) {
      throwIfAborted(signal);
      const bytes = new Uint8Array(
        await file.slice(offset, Math.min(offset + CHUNK_SIZE, file.size)).arrayBuffer(),
      );
      throwIfAborted(signal);
      const received = await invoke<number>("proxy_upload_chunk", {
        req: { upload_id: uploadId, file_data: bytesToBase64(bytes) },
      });
      throwIfAborted(signal);
      onProgress?.(Math.min(90, Math.round((received / file.size) * 90)));
    }
    throwIfAborted(signal);
    const response = await finishUpload(uploadId, signal);
    onProgress?.(100);
    return response;
  } catch (error) {
    await invoke("proxy_upload_abort", {
      req: { upload_id: uploadId },
    }).catch(() => undefined);
    throw error;
  }
}
