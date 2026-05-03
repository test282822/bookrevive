"use client";

import { useUser, SignInButton, SignOutButton } from "@clerk/nextjs";
import { useState, useRef, useCallback } from "react";
import UploadZone from "@/components/UploadZone";
import ProcessingCard from "@/components/ProcessingCard";
import ResultCard from "@/components/ResultCard";
import ApiKeyInput from "@/components/ApiKeyInput";

type Stage = "idle" | "processing" | "done" | "error";

export default function Home() {
  const { isSignedIn, user, isLoaded } = useUser();
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [epubUrl, setEpubUrl] = useState<string | null>(null);
  const [epubName, setEpubName] = useState("book.epub");
  const [error, setError] = useState<string | null>(null);

  const handleProcess = useCallback(async () => {
    if (!files.length || !title.trim()) return;

    setStage("processing");
    setError(null);

    try {
      // Get Clerk session token
      const token = await (window as any).Clerk?.session?.getToken();

      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      form.append("title", title.trim());
      form.append("author", author.trim() || "Unknown Author");
      form.append("language", "en");

      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (apiKey.trim()) headers["X-Anthropic-Key"] = apiKey.trim();

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/process`,
        { method: "POST", body: form, headers }
      );

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const slug = title.toLowerCase().replace(/\s+/g, "-").replace(/[^\w-]/g, "");
      setEpubUrl(url);
      setEpubName(`${slug}.epub`);
      setStage("done");
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
      setStage("error");
    }
  }, [files, title, author, apiKey]);

  const handleReset = () => {
    setFiles([]);
    setTitle("");
    setAuthor("");
    setStage("idle");
    setEpubUrl(null);
    setError(null);
  };

  if (!isLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-amber-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="fade-up">
      {/* Header */}
      <header className="sticky top-0 z-20 bg-stone-950/90 backdrop-blur border-b border-stone-800 px-4 py-3 flex items-center justify-between -mx-4">
        <div>
          <h1 className="font-serif text-xl text-amber-400 leading-none">BookRevive</h1>
          <p className="text-stone-500 text-xs mt-0.5">Old books, new life</p>
        </div>
        <div className="flex items-center gap-3">
          {isSignedIn ? (
            <>
              <span className="text-stone-400 text-xs hidden sm:block">
                {user.firstName || user.emailAddresses[0]?.emailAddress}
              </span>
              <SignOutButton>
                <button className="text-xs text-stone-400 border border-stone-700 rounded-full px-3 py-1 active:bg-stone-800">
                  Sign out
                </button>
              </SignOutButton>
            </>
          ) : (
            <SignInButton mode="modal">
              <button className="text-xs bg-amber-500 text-stone-950 font-semibold rounded-full px-4 py-1.5 active:bg-amber-400">
                Sign in
              </button>
            </SignInButton>
          )}
        </div>
      </header>

      {/* AD SLOT — top inline (enable when AdSense approved) */}
      {/* <div className="my-4 h-14 bg-stone-900 rounded-xl flex items-center justify-center text-stone-700 text-xs">Ad</div> */}

      <div className="mt-6 space-y-5">
        {stage === "idle" && (
          <>
            <UploadZone files={files} onChange={setFiles} />

            {files.length > 0 && (
              <div className="space-y-3 fade-up">
                <div>
                  <label className="text-xs text-stone-400 uppercase tracking-wider block mb-1.5">
                    Book Title *
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Oliver Twist"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full bg-stone-900 border border-stone-700 rounded-xl px-4 py-3 text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-500 text-base"
                  />
                </div>
                <div>
                  <label className="text-xs text-stone-400 uppercase tracking-wider block mb-1.5">
                    Author
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Charles Dickens"
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    className="w-full bg-stone-900 border border-stone-700 rounded-xl px-4 py-3 text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-500 text-base"
                  />
                </div>

                {isSignedIn && (
                  <ApiKeyInput value={apiKey} onChange={setApiKey} />
                )}

                {!isSignedIn && (
                  <div className="bg-stone-900 border border-stone-700 rounded-xl p-4 text-center">
                    <p className="text-stone-400 text-sm mb-3">
                      Sign in to process books and use your Anthropic key for better OCR on hard-to-read pages.
                    </p>
                    <SignInButton mode="modal">
                      <button className="bg-amber-500 text-stone-950 font-semibold rounded-full px-6 py-2 text-sm active:bg-amber-400">
                        Sign in to continue
                      </button>
                    </SignInButton>
                  </div>
                )}

                {isSignedIn && (
                  <button
                    onClick={handleProcess}
                    disabled={!title.trim()}
                    className="w-full bg-amber-500 disabled:bg-stone-800 disabled:text-stone-600 text-stone-950 font-semibold rounded-2xl py-4 text-base active:bg-amber-400 transition-colors"
                  >
                    {title.trim() ? `Digitize ${files.length} page${files.length > 1 ? "s" : ""}` : "Enter a title to continue"}
                  </button>
                )}
              </div>
            )}
          </>
        )}

        {stage === "processing" && <ProcessingCard pageCount={files.length} />}

        {stage === "done" && epubUrl && (
          <ResultCard
            epubUrl={epubUrl}
            epubName={epubName}
            title={title}
            pageCount={files.length}
            onReset={handleReset}
          />
        )}

        {stage === "error" && (
          <div className="bg-red-950/50 border border-red-800 rounded-2xl p-5 fade-up">
            <p className="text-red-400 font-medium mb-1">Something went wrong</p>
            <p className="text-red-300/70 text-sm mb-4">{error}</p>
            <button
              onClick={handleReset}
              className="text-sm text-stone-400 border border-stone-700 rounded-full px-4 py-1.5 active:bg-stone-800"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      {/* AD SLOT — bottom inline */}
      {/* <div className="mt-8 h-14 bg-stone-900 rounded-xl flex items-center justify-center text-stone-700 text-xs">Ad</div> */}

      <footer className="mt-12 text-center text-stone-700 text-xs pb-safe">
        BookRevive — open source on GitHub
      </footer>
    </div>
  );
}
