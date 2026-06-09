import "./ChatDialog.css";
import React, { useState, useRef } from "react";
import ConversationList from "./ConversationList";
import MessagePanel from "./MessagePanel";
import { messageAPI } from "./messageService";
import type { Conversation } from "./useConversation";

import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";

type Props = {
  onClose: () => void;
  list: Conversation[];
  refetch: () => void;
};

const ChatDialog: React.FC<Props> = ({ onClose, list, refetch }) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const handleSelect = async (email: string) => {
    setSelected(email);

    await messageAPI.markRead(email);

    refetch();
  };

  return (
    <div ref={dialogRef} className="chat-dialog">
      <ConversationList
        list={list}
        selected={selected}
        onSelect={handleSelect}
      />

      {selected ? (
        <MessagePanel otherEmail={selected} />
      ) : (
        <div className="empty-chat">
          <div className="empty-chat-logo">
            <ForumOutlinedIcon className="chat-main-icon" />

            <div className="ai-star">
              <AutoAwesomeIcon />
            </div>
          </div>

          <h2>Bắt đầu trò chuyện ngay</h2>

          <p>
            Kết nối, trò chuyện và trao đổi cùng sinh viên trong cộng đồng.
          </p>
        </div>
      )}
    </div>
  );
};

export default ChatDialog;