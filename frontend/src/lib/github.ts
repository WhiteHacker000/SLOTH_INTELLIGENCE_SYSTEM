/** Short label for a GitHub link, e.g. "PR #12 comment" or "Issue #7". */
export function sourceLabel(url: string): string {
  const match = url.match(/\/(issues|pull)\/(\d+)(#.*)?$/);
  if (!match) return "GitHub";
  const kind = match[1] === "pull" ? "PR" : "Issue";
  const part = match[3]?.startsWith("#pullrequestreview")
    ? " review"
    : match[3]
      ? " comment"
      : "";
  return `${kind} #${match[2]}${part}`;
}
