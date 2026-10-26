import { Fragment } from "react";

const URL_RE = /(https?:\/\/[^\s<>"']+)/g;

export const hasUrl = (text: string) => /https?:\/\//.test(text);

/** Текст с кликабельными ссылками (без dangerouslySetInnerHTML). */
export function Linkified({ text }: { text: string }) {
  return (
    <>
      {text.split(URL_RE).map((part, i) =>
        i % 2 ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}
