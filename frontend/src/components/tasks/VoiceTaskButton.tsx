
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

type RecordingState =
  | "idle"
  | "recording"
  | "uploading";

export default function VoiceTaskButton() {
  const queryClient = useQueryClient();

  const [status, setStatus] =
    useState<RecordingState>("idle");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const stopTracks = () => {
    streamRef.current?.getTracks().forEach(
      (track) => track.stop()
    );
    streamRef.current = null;
  };

  useEffect(() => {
    return () => {
      recorderRef.current?.stop();
      stopTracks();
    };
  }, []);

  const startRecording = async () => {
    setError("");
    setMessage("");

    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stopTracks();

        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType,
        });

        if (blob.size === 0) {
          setError("No audio was recorded.");
          setStatus("idle");
          return;
        }

        setStatus("uploading");

        try {
          const extension = recorder.mimeType.includes("mp4")
            ? "m4a"
            : "webm";

          const form = new FormData();
          form.append(
            "file",
            blob,
            `recording.${extension}`
          );

          const response = await fetch(
            "/api/v1/tasks/voice",
            {
              method: "POST",
              credentials: "include",
              body: form,
            }
          );

          if (!response.ok) {
            throw new Error(
              "Unable to create task from recording."
            );
          }

          await queryClient.invalidateQueries({
            queryKey: ["tasks"],
          });

          setMessage("Voice task created successfully.");
        } catch {
          setError(
            "Voice transcription failed. Please try again."
          );
        } finally {
          setStatus("idle");
        }
      };

      recorder.start();
      setStatus("recording");
    } catch {
      setError(
        "Microphone access denied or unavailable."
      );
    }
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  };

  return (
    <div className="voice-task-control">
      <button
        type="button"
        className={
          status === "recording"
            ? "voice-task-button recording"
            : "voice-task-button"
        }
        onClick={
          status === "recording"
            ? stopRecording
            : startRecording
        }
        disabled={status === "uploading"}
      >
        {status === "recording"
          ? "■ Stop recording"
          : status === "uploading"
            ? "Transcribing..."
            : "🎙 Voice task"}
      </button>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {message && (
        <p className="voice-task-success" role="status">
          {message}
        </p>
      )}
    </div>
  );
}
