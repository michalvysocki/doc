export function getFileLabel(mimeType) {
  if (mimeType === "application/pdf") return "PDF";
  if (mimeType.includes("wordprocessingml")) return "DOCX";
  if (mimeType.includes("spreadsheetml")) return "XLSX";
  if (mimeType.includes("presentationml")) return "PPTX";
  if (mimeType.startsWith("text/")) return "TXT";
  return "FILE";
}

export function getFileLabelFromName(filename) {
  const extension = filename.split(".").pop().toUpperCase();
  return extension && extension !== filename.toUpperCase() ? extension : "FILE";
}

export default getFileLabel;
