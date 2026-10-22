import AttachmentCard from "./AttachmentCard";
import getFileLabel from "../utils/fileLabel";
import { fileContentUrl } from "../utils/api";

function AttachmentList({ documents, removeDocument }) {
  return (
    <div className="flex gap-2 overflow-x-auto px-4 pb-2 pt-2">
      {documents.map((doc) => (
        <AttachmentCard
          key={doc.file_uuid}
          name={doc.filename}
          thumbnail={doc.media_type ? fileContentUrl(doc.file_uuid) : null}
          typeLabel={getFileLabel(doc.type)}
          onRemove={() => removeDocument(doc.file_uuid)}
        />
      ))}
    </div>
  );
}

export default AttachmentList;
