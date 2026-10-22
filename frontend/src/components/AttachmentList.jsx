import { FileText, X } from "lucide-react";
import AttachmentCard from "./AttachmentCard";
import getFileLabel from "../utils/fileLabel";

function AttachmentList({ documents, images, removeDocument, removeImage }) {
  return (
    <div className="flex gap-2 overflow-x-auto px-4 pb-2 pt-2">
      {documents.map((doc) => (
        <AttachmentCard
          key={doc.file_uuid}
          name={doc.filename}
          typeLabel={getFileLabel(doc.type)}
          onRemove={() => removeDocument(doc.file_uuid)}
        />
      ))}

      {images.map((img) => (
        <AttachmentCard
          key={img.id}
          name={img.filename}
          thumbnail={img.data}
          onRemove={() => removeImage(img.id)}
        />
      ))}
    </div>
  );
}

export default AttachmentList;
