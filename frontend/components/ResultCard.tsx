"use client";

interface Props {
  epubUrl: string;
  epubName: string;
  title: string;
  pageCount: number;
  onReset: () => void;
}

export default function ResultCard({ epubUrl, epubName, title, pageCount, onReset }: Props) {

  const handleDownload = () => {
    // Safari iPhone compatible download
    // Creates a temporary link and forces click
    fetch(epubUrl)
      .then(res => res.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        a.download = epubName;
        document.body.appendChild(a);
        a.click();
        // Safari fallback — open in new tab if download doesnt trigger
        setTimeout(() => {
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        }, 1000);
      })
      .catch(() => {
        // Final fallback — open directly in browser
        window.open(epubUrl, "_blank");
      });
  };

  return (
    <div className="bg-stone-900 border border-stone-700 rounded-2xl p-6 space-y-5 fade-up">
      {/* Success icon */}
      <div className="text-center">
        <div className="text-5xl mb-3">✅</div>
        <h2 className="font-serif text-xl text-amber-400">{title}</h2>
        <p className="text-stone-400 text-sm mt-1">
          {pageCount} page{pageCount > 1 ? "s" : ""} digitized successfully
        </p>
      </div>

      {/* Primary download button */}
      <button
        onClick={handleDownload}
        className="block w-full bg-amber-500 text-stone-950 font-semibold rounded-2xl py-4 text-center text-base active:bg-amber-400 transition-colors"
      >
        Download EPUB
      </button>

      {/* Safari fallback — direct link opens in Books app */}
      <a
        href={epubUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full text-center text-amber-600 text-sm underline py-1"
      >
        Tap here if download doesn't start
      </a>

      <p className="text-stone-600 text-xs text-center">
        Opens in Apple Books, Kindle, or any EPUB reader
      </p>

      {/* AD SLOT */}
      {/* <AdSlot slot="result-inline" /> */}

      <button
        onClick={onReset}
        className="w-full text-stone-500 border border-stone-800 rounded-2xl py-3 text-sm active:bg-stone-900"
      >
        Digitize another book
      </button>
    </div>
  );
}
