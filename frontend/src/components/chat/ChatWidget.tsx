"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Loader2,
  MessageCircle,
  Mic,
  Paperclip,
  Send,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { startWavCapture } from "@/lib/audioWav";
import {
  sendChatMessage,
  handleApiError,
  type ChatHistoryMessage,
} from "@/lib/api";
import type { AxiosError } from "axios";

type UiMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  imageUrls?: string[];
};

const MAX_IMAGES = 5;
const MAX_VIDEO_FRAMES = 3;

function blobToRawBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onloadend = () => {
      const s = r.result as string;
      const i = s.indexOf("base64,");
      resolve(i >= 0 ? s.slice(i + 7) : s);
    };
    r.onerror = () => reject(new Error("read failed"));
    r.readAsDataURL(blob);
  });
}

async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onloadend = () => resolve(r.result as string);
    r.onerror = () => reject(new Error("read failed"));
    r.readAsDataURL(file);
  });
}

function looksLikeImage(f: File): boolean {
  if (f.type.startsWith("image/")) return true;
  return /\.(png|jpe?g|jfif|pjpeg|gif|webp|bmp|avif|svg|ico|heic|heif|tiff?)$/i.test(
    f.name,
  );
}

function looksLikeVideo(f: File): boolean {
  if (f.type.startsWith("video/")) return true;
  return /\.(mp4|webm|mov|mkv|avi|m4v)$/i.test(f.name);
}

/** Downscale large photos so previews and JSON payloads stay reliable in the browser. */
async function imageFileToPreviewDataUrl(
  file: File,
  maxDim = 1600,
  quality = 0.88,
): Promise<string> {
  if (typeof createImageBitmap !== "undefined") {
    try {
      const bitmap = await createImageBitmap(file);
      try {
        let w = bitmap.width;
        let h = bitmap.height;
        if (!w || !h) throw new Error("Invalid size");
        if (w > maxDim || h > maxDim) {
          if (w >= h) {
            h = Math.round((h * maxDim) / w);
            w = maxDim;
          } else {
            w = Math.round((w * maxDim) / h);
            h = maxDim;
          }
        }
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("No canvas");
        ctx.drawImage(bitmap, 0, 0, w, h);
        const dataUrl = canvas.toDataURL("image/jpeg", quality);
        if (!dataUrl || dataUrl === "data:,") throw new Error("Empty canvas");
        return dataUrl;
      } finally {
        bitmap.close();
      }
    } catch {
      /* fall through to Image() + object URL */
    }
  }

  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("Could not decode image"));
      img.src = url;
    });
    let w = img.naturalWidth;
    let h = img.naturalHeight;
    if (!w || !h) throw new Error("Invalid image size");
    if (w > maxDim || h > maxDim) {
      if (w >= h) {
        h = Math.round((h * maxDim) / w);
        w = maxDim;
      } else {
        w = Math.round((w * maxDim) / h);
        h = maxDim;
      }
    }
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("No canvas");
    ctx.drawImage(img, 0, 0, w, h);
    const dataUrl = canvas.toDataURL("image/jpeg", quality);
    if (!dataUrl || dataUrl === "data:,") throw new Error("Empty canvas");
    return dataUrl;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function videoFileToKeyframeDataUrls(file: File): Promise<string[]> {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.src = url;
  video.muted = true;
  video.playsInline = true;
  try {
    await new Promise<void>((resolve, reject) => {
      video.onloadeddata = () => resolve();
      video.onerror = () => reject(new Error("Could not load video"));
    });
    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    const times =
      duration > 0.5
        ? [0.1, duration * 0.5, Math.max(duration - 0.2, 0.2)]
        : [0];
    const clamped = times.map((t) =>
      Math.min(Math.max(t, 0), Math.max(duration - 0.05, 0)),
    );
    const unique = Array.from(new Set(clamped)).slice(0, MAX_VIDEO_FRAMES);

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return [];

    const out: string[] = [];
    for (const t of unique) {
      await new Promise<void>((resolve) => {
        const done = () => {
          video.removeEventListener("seeked", done);
          resolve();
        };
        video.addEventListener("seeked", done);
        video.currentTime = t;
      });
      const vw = video.videoWidth || 640;
      const vh = video.videoHeight || 360;
      const maxW = 1024;
      let w = vw;
      let h = vh;
      if (w > maxW) {
        h = Math.round((h * maxW) / w);
        w = maxW;
      }
      canvas.width = w;
      canvas.height = h;
      ctx.drawImage(video, 0, 0, w, h);
      out.push(canvas.toDataURL("image/jpeg", 0.82));
      if (out.length >= MAX_VIDEO_FRAMES) break;
    }
    return out;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const [pendingAudio, setPendingAudio] = useState<{
    base64: string;
    mime: string;
  } | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const wavStopRef = useRef<(() => void) | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    if (!open) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [open, messages, isSending]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (wavStopRef.current) {
        try {
          wavStopRef.current();
        } catch {
          /* ignore */
        }
        wavStopRef.current = null;
      }
    };
  }, []);

  const addAttachmentFromFile = useCallback(async (file: File) => {
    setInlineError(null);
    try {
      if (looksLikeImage(file)) {
        let url: string;
        try {
          url = await imageFileToPreviewDataUrl(file);
        } catch {
          url = await fileToDataUrl(file);
        }
        setPendingImages((prev) => [...prev, url].slice(0, MAX_IMAGES));
      } else if (looksLikeVideo(file)) {
        const frames = await videoFileToKeyframeDataUrls(file);
        if (!frames.length) {
          toast.error("Could not extract video frames", {
            description: "Try another clip or attach images.",
          });
          return;
        }
        setPendingImages((prev) => [...prev, ...frames].slice(0, MAX_IMAGES));
      } else {
        toast.info("Unsupported file", {
          description: "Use an image or video.",
        });
      }
    } catch {
      toast.error("Could not read that file.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (wavStopRef.current) {
      try {
        wavStopRef.current();
      } catch {
        /* ignore */
      }
      wavStopRef.current = null;
    }
    setIsRecording(false);
  }, []);

  const startRecording = useCallback(async () => {
    setInlineError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setInlineError("Microphone is not supported in this browser.");
      return;
    }
    if (typeof AudioContext === "undefined" && typeof (window as unknown as { webkitAudioContext?: unknown }).webkitAudioContext === "undefined") {
      setInlineError("Audio recording is not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const { stop } = await startWavCapture(
        stream,
        async (blob) => {
          if (!mountedRef.current) return;
          if (blob.size < 64) return;
          try {
            const base64 = await blobToRawBase64(blob);
            if (!mountedRef.current) return;
            setPendingAudio({ base64, mime: blob.type || "audio/wav" });
          } catch {
            if (mountedRef.current) setInlineError("Could not read the recording.");
          }
        },
        (err) => {
          if (mountedRef.current) setInlineError(err.message || "Recording failed.");
        },
      );
      wavStopRef.current = stop;
      setIsRecording(true);
    } catch (e) {
      const m = e instanceof Error ? e.message : "";
      if (m.includes("WAV") || m.includes("ScriptProcessor")) {
        setInlineError(m);
      } else {
        setInlineError("Microphone permission was denied or unavailable.");
      }
    }
  }, []);

  const onMicClick = useCallback(() => {
    if (isRecording) stopRecording();
    else void startRecording();
  }, [isRecording, startRecording, stopRecording]);

  const onFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      // Copy to a real array BEFORE clearing the input — some browsers
      // (Chromium included) invalidate the FileList when value is reset.
      const files = Array.from(e.target.files ?? []);
      e.target.value = "";
      if (!files.length) return;
      for (const file of files) {
        await addAttachmentFromFile(file);
      }
    },
    [addAttachmentFromFile],
  );

  const pendingAudioDataUrl = useMemo(() => {
    if (!pendingAudio) return null;
    return `data:${pendingAudio.mime};base64,${pendingAudio.base64}`;
  }, [pendingAudio]);

  const onComposerPaste = useCallback(
    async (e: React.ClipboardEvent) => {
      const fromFiles = e.clipboardData?.files;
      if (fromFiles?.length) {
        let handled = false;
        for (const f of Array.from(fromFiles)) {
          if (looksLikeImage(f) || looksLikeVideo(f)) {
            e.preventDefault();
            await addAttachmentFromFile(f);
            handled = true;
          }
        }
        if (handled) return;
      }
      const items = e.clipboardData?.items;
      if (!items) return;
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it.kind !== "file") continue;
        const f = it.getAsFile();
        if (!f || (!looksLikeImage(f) && !looksLikeVideo(f))) continue;
        e.preventDefault();
        await addAttachmentFromFile(f);
        break;
      }
    },
    [addAttachmentFromFile],
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text && pendingImages.length === 0 && !pendingAudio) return;

    const sendImages = [...pendingImages];
    const sendAudio = pendingAudio;
    const userDisplayText =
      text ||
      (sendImages.length
        ? "(Image attachment)"
        : sendAudio
          ? "Voice message"
          : "");

    let lastApiText = text;
    if (!lastApiText && sendImages.length) lastApiText = "(Image attachment)";
    if (!lastApiText && sendAudio && !sendImages.length) lastApiText = "";

    const userMsg: UiMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: userDisplayText,
      imageUrls: sendImages.length ? sendImages : undefined,
    };

    const nextThread = [...messages, userMsg];
    setMessages(nextThread);
    setInput("");
    setPendingImages([]);
    setPendingAudio(null);
    setInlineError(null);
    setIsSending(true);

    const apiMessages: ChatHistoryMessage[] = [
      ...messages.map((m) => ({ role: m.role, text: m.text })),
      { role: "user", text: lastApiText },
    ];

    try {
      const data = await sendChatMessage({
        messages: apiMessages,
        images: sendImages.length ? sendImages : undefined,
        audio_base64: sendAudio?.base64,
        audio_mime: sendAudio?.mime,
      });
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", text: data.message },
      ]);
    } catch (err) {
      let msg =
        (err as AxiosError)?.response?.data != null
          ? handleApiError(err as AxiosError)
          : (err as Error)?.message || "Request failed";
      if (/balance.*audio|audio.*balance|requires at least.*\$[\d.]+.*balance/i.test(msg)) {
        msg +=
          " OpenRouter often requires paid credits for audio input. Add credits to your account, or ask in text-only mode instead.";
      }
      setInlineError(msg);
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
      setPendingImages(sendImages);
      if (sendAudio) setPendingAudio(sendAudio);
      if (text) setInput(text);
    } finally {
      setIsSending(false);
    }
  }, [input, messages, pendingAudio, pendingImages]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isSending) void handleSend();
    }
  };

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex flex-col items-end gap-3">
      {open && (
        <div className="pointer-events-auto flex h-[min(520px,70vh)] w-[min(100vw-2rem,380px)] flex-col overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-xl">
          <header className="flex shrink-0 items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold">NewsFlow assistant</span>
              <span className="text-xs text-muted-foreground">
                Paste or drop media here · WAV voice preview · OpenRouter
              </span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 rounded-full"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
            >
              <X className="h-4 w-4" />
            </Button>
          </header>

          <div
            ref={scrollRef}
            className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3"
          >
            {messages.length === 0 && !isSending && (
              <p className="rounded-2xl rounded-bl-md border border-dashed border-border bg-muted/30 px-3 py-2 text-center text-xs text-muted-foreground">
                Ask about tech news, summaries, or how to use NewsFlow. Attach
                screenshots, video key frames, or a short voice note.
              </p>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "flex w-full",
                  m.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[92%] space-y-2 px-3 py-2 text-sm leading-relaxed shadow-sm",
                    m.role === "user"
                      ? "rounded-2xl rounded-br-md bg-primary text-primary-foreground"
                      : "rounded-2xl rounded-bl-md bg-muted text-foreground",
                  )}
                >
                  {m.imageUrls && m.imageUrls.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {m.imageUrls.map((src, i) => (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={i}
                          src={src}
                          alt=""
                          className="max-h-32 max-w-[min(100%,200px)] rounded-lg border border-black/15 bg-background object-contain dark:border-white/20"
                        />
                      ))}
                    </div>
                  )}
                  <p className="whitespace-pre-wrap break-words">{m.text}</p>
                </div>
              </div>
            ))}
            {isSending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-muted px-3 py-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="inline-flex gap-1">
                    <span className="animate-pulse">Thinking</span>
                    <span className="opacity-60">…</span>
                  </span>
                </div>
              </div>
            )}
          </div>

          {inlineError && (
            <div className="shrink-0 border-t border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {inlineError}
            </div>
          )}

          {(pendingImages.length > 0 || pendingAudio) && (
            <div className="flex shrink-0 flex-wrap items-start gap-2 border-t border-border px-3 py-2">
              {pendingImages.map((src, i) => (
                <div key={`${i}-${src.slice(0, 48)}`} className="relative shrink-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={src}
                    alt=""
                    className="h-16 w-16 rounded-lg border border-border bg-muted object-cover"
                  />
                  <button
                    type="button"
                    className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-background text-xs shadow ring-1 ring-border hover:bg-muted"
                    onClick={() =>
                      setPendingImages((p) => p.filter((_, j) => j !== i))
                    }
                    aria-label="Remove image"
                  >
                    ×
                  </button>
                </div>
              ))}
              {pendingAudio && pendingAudioDataUrl && (
                <div className="flex min-w-0 flex-1 flex-col gap-1.5 rounded-lg border border-border bg-muted/50 px-2 py-2 text-xs">
                  <div className="flex items-center gap-2">
                    <Mic className="h-3.5 w-3.5 shrink-0" />
                    <span className="font-medium">Voice note</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="ml-auto h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
                      onClick={() => setPendingAudio(null)}
                      aria-label="Remove voice note"
                      title="Remove voice note"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <audio
                    controls
                    src={pendingAudioDataUrl}
                    className="h-9 w-full max-w-full"
                  >
                    Your browser does not support audio preview.
                  </audio>
                </div>
              )}
            </div>
          )}

          <footer
            className="shrink-0 border-t border-border p-2"
            onDragOver={(ev) => {
              ev.preventDefault();
              ev.stopPropagation();
            }}
            onDrop={(ev) => {
              ev.preventDefault();
              ev.stopPropagation();
              const dropped = ev.dataTransfer.files;
              if (dropped?.length) {
                for (const f of Array.from(dropped)) void addAttachmentFromFile(f);
              }
            }}
          >
            <div className="flex items-end gap-1.5">
              <input
                ref={fileRef}
                type="file"
                accept="image/*,video/*"
                multiple
                className="hidden"
                onChange={onFileChange}
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-xl"
                onClick={() => fileRef.current?.click()}
                disabled={isSending}
                aria-label="Attach image or video"
                title="Image or video (uses key frames)"
              >
                <Paperclip className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant={isRecording ? "destructive" : "outline"}
                size="icon"
                className="h-10 w-10 shrink-0 rounded-xl"
                onClick={onMicClick}
                disabled={isSending}
                aria-label={isRecording ? "Stop recording" : "Record voice"}
                title={isRecording ? "Stop recording" : "Record voice (WAV — preview before send)"}
              >
                {isRecording ? (
                  <Square className="h-3.5 w-3.5 fill-current" />
                ) : (
                  <Mic className="h-4 w-4" />
                )}
              </Button>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPaste={onComposerPaste}
                onKeyDown={onKeyDown}
                placeholder="Message..."
                rows={2}
                disabled={isSending}
                className="min-h-[2.5rem] flex-1 resize-none rounded-xl border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <Button
                type="button"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-xl"
                onClick={() => void handleSend()}
                disabled={
                  isSending ||
                  (!input.trim() && pendingImages.length === 0 && !pendingAudio)
                }
                aria-label="Send"
              >
                {isSending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </footer>
        </div>
      )}

      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setInlineError(null);
        }}
        className={cn(
          "pointer-events-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg ring-2 ring-primary/30 transition hover:bg-primary/90 hover:ring-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          open && "ring-offset-2",
        )}
        aria-label={open ? "Close assistant" : "Open assistant"}
        aria-expanded={open}
      >
        {open ? (
          <X className="h-6 w-6" />
        ) : (
          <MessageCircle className="h-6 w-6" />
        )}
      </button>
    </div>
  );
}
