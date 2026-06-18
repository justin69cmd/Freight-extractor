// Save a Blob to disk. Where supported (Chromium: Chrome/Edge/Brave/Arc), uses the
// File System Access API so the user gets a native "Save As" dialog and picks the
// folder + filename. Falls back to a normal browser download (Downloads folder)
// elsewhere.
export async function saveBlob(blob: Blob, suggestedName: string): Promise<"picked" | "downloaded" | "cancelled"> {
  const picker = (window as unknown as {
    showSaveFilePicker?: (opts: unknown) => Promise<{
      createWritable: () => Promise<{ write: (b: Blob) => Promise<void>; close: () => Promise<void> }>;
    }>;
  }).showSaveFilePicker;

  if (picker) {
    try {
      const handle = await picker({
        suggestedName,
        types: [
          {
            description: "Excel Workbook",
            accept: { "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return "picked";
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return "cancelled"; // user closed dialog
      // otherwise fall through to the anchor download
    }
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return "downloaded";
}
