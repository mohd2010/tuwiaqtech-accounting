import { useEffect, useRef, useCallback } from "react";

/**
 * Listens for rapid keystrokes (barcode scanner acting as HID keyboard).
 * When Enter is pressed and the buffer has > 3 chars, fires `onScan`.
 * A 50 ms inter-keystroke timeout distinguishes scanner input from manual typing.
 */
export function useBarcodeScanner(onScan: (barcode: string) => void) {
  const bufferRef = useRef("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  const reset = useCallback(() => {
    bufferRef.current = "";
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Ignore if user is typing in an input/textarea (manual barcode field handles itself)
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "Enter") {
        if (bufferRef.current.length > 3) {
          onScanRef.current(bufferRef.current);
        }
        reset();
        return;
      }

      // Only accept printable single characters
      if (e.key.length === 1) {
        bufferRef.current += e.key;

        // Reset timeout — if next key doesn't arrive within 50 ms, it's manual typing
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(reset, 50);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      reset();
    };
  }, [reset]);
}
