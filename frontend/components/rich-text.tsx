// Teks respons backend: baris biasa + tautan sitasi markdown [SOURCE-ID](url) dirender jadi chip.
const LINK = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

export function RichText({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(LINK)) {
    parts.push(text.slice(last, m.index));
    parts.push(
      <a
        key={m.index}
        href={m[2]}
        target="_blank"
        rel="noopener noreferrer"
        className="mx-0.5 inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 align-baseline text-xs font-medium text-foreground underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
      >
        {m[1]}
      </a>,
    );
    last = m.index + m[0].length;
  }
  parts.push(text.slice(last));
  return <div className="whitespace-pre-wrap break-words">{parts}</div>;
}
