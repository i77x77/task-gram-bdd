import { useEffect, useRef, useState } from "react";

const DB = "taskgram-ui";
const STORE = "kv";
const KEY = "background";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idb<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function apply(blob: Blob | null) {
  const root = document.documentElement;
  const prev = root.dataset.bgUrl;
  if (prev) URL.revokeObjectURL(prev);
  if (blob) {
    const url = URL.createObjectURL(blob);
    root.dataset.bgUrl = url;
    root.style.setProperty("--bg-image", `url("${url}")`);
    root.classList.add("custom-bg");
  } else {
    delete root.dataset.bgUrl;
    root.style.removeProperty("--bg-image");
    root.classList.remove("custom-bg");
  }
}

/** Свой фон доски: картинка хранится в IndexedDB браузера (на сервер не уходит). */
export function BackgroundPicker() {
  const input = useRef<HTMLInputElement>(null);
  const [has, setHas] = useState(false);

  useEffect(() => {
    idb<Blob | undefined>("readonly", (s) => s.get(KEY))
      .then((b) => {
        if (b) {
          apply(b);
          setHas(true);
        }
      })
      .catch(() => {});
  }, []);

  const pick = async (file?: File) => {
    if (!file || !file.type.startsWith("image/")) return;
    apply(file);
    setHas(true);
    await idb("readwrite", (s) => s.put(file, KEY)).catch(() => {});
  };

  const reset = async () => {
    apply(null);
    setHas(false);
    await idb("readwrite", (s) => s.delete(KEY)).catch(() => {});
  };

  return (
    <>
      <input ref={input} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />
      <button onClick={() => input.current?.click()}>🖼 Фон</button>
      {has && (
        <button onClick={reset} title="Вернуть стандартный фон">
          Сбросить фон
        </button>
      )}
    </>
  );
}
