import React, { useEffect, useState } from "react";
import FileService from "../../../../services/FileService";

type Props = { fileId: string };

const ChatImage: React.FC<Props> = ({ fileId }) => {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const fileUrl = FileService.getFileUrl(fileId);
    setUrl(fileUrl);
  }, [fileId]);

  if (!url)
    return <span className="chat-img-placeholder">Loading...</span>;

  return <img src={url} alt="media" className="chat-img" />;
};

export default ChatImage;