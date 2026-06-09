import { useEffect, useState } from "react";
import { messageAPI } from "./messageService";
import useWebSocket from "./useWebSocket";
import { useAuth } from "./AuthContext";

export type Message = {
  id?: string;
  _id?: string; // ✅ FIX: thêm _id
  sender_email: string;
  receiver_email: string;
  content: string;
  file?: string[];
  media?: string[];
  created_at: string;
  mine: boolean;
};

export default function useChat(otherEmail: string) {
  const { email } = useAuth();
  const realtime = useWebSocket(localStorage.getItem("token") || "");
  const [history, setHistory] = useState<Message[]>([]);

  /* ---------- load history ---------- */
  useEffect(() => {
    (async () => {
      const { data } = await messageAPI.getConversation(otherEmail);

      setHistory(
        data.map((m: any) => ({
          ...m,
          id: m._id || m.id,
          file: m.file ?? [],
          media: m.media ?? [], // ✅ đã là URL rồi
          mine: m.sender_email === email,
        }))
      );
    })();
  }, [otherEmail, email]);

  /* ---------- mark-read ---------- */
  useEffect(() => {
    if (otherEmail) {
      messageAPI.markRead(otherEmail);
    }
  }, [otherEmail]);

  /* ---------- realtime ---------- */
  useEffect(() => {
    if (!realtime.length) return;

    realtime.forEach((m: any) => {
      const isMatch =
        (m.sender_email === otherEmail && m.receiver_email === email) ||
        (m.sender_email === email && m.receiver_email === otherEmail);

      if (!isMatch) return;

      const id = m._id || m.id;

      setHistory((h) => {
        const exists = h.some((x) => x.id === id);
        if (exists) return h;

        return [
          ...h,
          {
            ...m,
            id,
            file: m.file ?? [],
            media: m.media ?? [], // ✅ URL backend luôn
            mine: m.sender_email === email,
          },
        ];
      });

      if (m.sender_email === otherEmail) {
        messageAPI.markRead(otherEmail);
      }
    });
  }, [realtime, otherEmail, email]);

  /* ---------- SEND MESSAGE (FIXED) ---------- */
  const sendMessage = async (
    content: string,
    file?: string[],
    media?: string[]
  ) => {
    if (!content.trim() && !file?.length && !media?.length) return;

    const tempId = `temp-${Date.now()}`;

    const tempMessage: Message = {
      id: tempId,
      sender_email: email,
      receiver_email: otherEmail,
      content,
      file: file ?? [],
      media: media ?? [],
      created_at: new Date().toISOString(),
      mine: true,
    };

    // 1. optimistic UI
    setHistory((h) => [...h, tempMessage]);

    // 2. call API
    const res = await messageAPI.send(otherEmail, {
      content,
      file,
      media,
    });

    const real = res.data;

    const realMessage: Message = {
      ...real,
      id: real._id || real.id,
      file: real.file ?? [],
      media: real.media ?? [], // ✅ dùng thẳng URL MinIO
      mine: true,
    };

    // 3. replace temp
    setHistory((h) =>
      h.map((m) => (m.id === tempId ? realMessage : m))
    );
  };

  /* ---------- sort ---------- */
  const sorted = [...history].sort(
    (a, b) =>
      new Date(a.created_at).getTime() -
      new Date(b.created_at).getTime()
  );

  return {
    messages: sorted,
    sendMessage,
  };
}