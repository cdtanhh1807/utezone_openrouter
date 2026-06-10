import "./profile.css";
import { useParams } from "react-router-dom";
import { useState, useRef, useEffect, useMemo } from "react";
import ProfileHeader from "./profileHeader";
import logochat from "../../../../assets/logochat.png";
import ProfilePosts from "./profilePost";
import ProfileArchived from "./profileArchived";
import ProfileAlbum from "./profileAlbum";
import ProfileSaved from "./profileSaved";
import StoryBlock from "../create/storyBlock";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import ArticleIcon from "@mui/icons-material/Article";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import InventoryIcon from "@mui/icons-material/Inventory";
import BookmarkBorderIcon from "@mui/icons-material/BookmarkBorder";
import BookmarkIcon from "@mui/icons-material/Bookmark";
import PhotoLibraryOutlinedIcon from "@mui/icons-material/PhotoLibraryOutlined";
import EventIcon from "@mui/icons-material/Event";

import ChatDialog from "../chat/ChatDialog";
import useConversations from "../chat/useConversation";
import { jwtDecode } from "jwt-decode";
import ProfileCatalog from "./profileCatalog";

function Profile() {
  const { email } = useParams<{ email: string }>();

  const [openMessage, setOpenMessage] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "posts" | "album" | "archived" | "saved" | "catalog"
  >("posts");

  const boxRef = useRef<HTMLDivElement>(null);

  const token = localStorage.getItem("token");
  let currentUserEmail: string | null = null;

  if (!currentUserEmail && token) {
    try {
      interface JwtPayload {
        sub: string;
        role: string;
        exp: number;
        per: string;
      }
      const decoded: JwtPayload = jwtDecode<JwtPayload>(token);
      currentUserEmail = decoded.sub;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }

  const { list, loading, refetch } = useConversations();

  // ✅ Tính số tin chưa đọc (an toàn + tối ưu)
  const unreadCount = useMemo(() => {
    return list?.filter((c) => c.has_new).length || 0;
  }, [list]);
  useEffect(() => {
    if (!openMessage) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpenMessage(false);
      }
    };
    console.log(
      "Đã thêm event listener cho click outside chat, email:",
      email,
      currentUserEmail,
    );
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [openMessage]);
  useEffect(() => {
    setActiveTab("posts");
  }, [email]);

  return (
    <div className="my-profile">
      {/* ===== MAIN CONTENT ===== */}
      <div className="profile-main">
        <div className="header">
          <ProfileHeader email={email} />
        </div>

        <div className="profile-body">
          <div className="storyBlock-profile">
            <StoryBlock />
          </div>

          {/* ===== TAB ===== */}
          <div className="profile-tabs">
            <button
              className={activeTab === "posts" ? "active" : ""}
              onClick={() => setActiveTab("posts")}
            >
              <ArticleOutlinedIcon />
            </button>

            <button
              className={activeTab === "album" ? "active" : ""}
              onClick={() => setActiveTab("album")}
            >
              <PhotoLibraryOutlinedIcon />
            </button>

            {email === currentUserEmail && (
              <button
                className={activeTab === "archived" ? "active" : ""}
                onClick={() => setActiveTab("archived")}
              >
                <Inventory2OutlinedIcon />
              </button>
            )}

            <button
              className={activeTab === "saved" ? "active" : ""}
              onClick={() => setActiveTab("saved")}
            >
              <BookmarkBorderIcon />
            </button>

            <button
              className={activeTab === "catalog" ? "active" : ""}
              onClick={() => setActiveTab("catalog")}
            >
              <EventIcon />
            </button>
          </div>

          {/* ===== CONTENT ===== */}
          <div className="p-post">
            {activeTab === "posts" && <ProfilePosts email={email} />}
            {activeTab === "album" && <ProfileAlbum email={email} />}
            {activeTab === "archived" && <ProfileArchived />}
            {activeTab === "saved" && <ProfileSaved email={email} />}
            {activeTab === "catalog" && <ProfileCatalog />}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Profile;
