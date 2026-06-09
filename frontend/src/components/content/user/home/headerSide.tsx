import "./headerSide.css";
import logo from "../../../../assets/logo.png";
import meeting_logo from "../../../../assets/meeting_logo.png";
import { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import SearchIcon from "@mui/icons-material/Search";
import NotificationsNoneIcon from "@mui/icons-material/NotificationsNone";
import { jwtDecode } from "jwt-decode";
import AccountService from "../../../../services/AccountService";
import NotificationModal from "../notification/notificationModal";
import PostDetail from "../post/postDetail";
import { postAPI } from "../../../../services/PostService";
import { useLocation } from "react-router-dom";
import logochat from "../../../../assets/logochat.png";
import useConversations from "../chat/useConversation";
import ChatDialog from "../chat/ChatDialog";
import VideoCameraFrontIcon from "@mui/icons-material/VideoCameraFront";
import ForumIcon from '@mui/icons-material/Forum';

const HeaderSide = () => {
  const [searchText, setSearchText] = useState("");
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [currentUserEmail, setCurrentUserEmail] = useState<string | null>(null);

  // --- NOTIFICATION ---
  const [openNotification, setOpenNotification] = useState(false);

  // --- POST DETAIL (🔥 ĐƯA LÊN CHA) ---
  const [isPostDetailOpen, setIsPostDetailOpen] = useState(false);
  const [activePost, setActivePost] = useState<any>(null);
  const [focusCommentId, setFocusCommentId] = useState<string | null>(null);
  const [openMessage, setOpenMessage] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  interface JwtPayload {
    sub: string;
    exp: number;
  }

  useEffect(() => {
    if (!token) return;

    try {
      const decoded: JwtPayload = jwtDecode(token);
      setCurrentUserEmail(decoded.sub);

      AccountService.get_account_info(decoded.sub)
        .then(setCurrentUser)
        .catch(console.error);
    } catch (err) {
      console.error("Token không hợp lệ", err);
    }
  }, [token]);
  const { list, loading, refetch } = useConversations();

  // ✅ Tính số tin chưa đọc (an toàn + tối ưu)
  const unreadCount = useMemo(() => {
    return list?.filter((c) => c.has_new).length || 0;
  }, [list]);

  // ================= CLICK OUTSIDE TO CLOSE CHAT =================
  useEffect(() => {
    if (!openMessage) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpenMessage(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [openMessage]);

  const handleSearch = () => {
    if (searchText.trim()) {
      navigate(`/search?keyword=${encodeURIComponent(searchText)}`);
      setSearchText("");
    }
  };
  const refreshPost = async (postId: string) => {
    const res = await postAPI.getById(postId);
    setActivePost(res.post || res);
  };
  const openOriginalPost = async (originalPostId: string) => {
    try {
      const res = await postAPI.getById(originalPostId);
      const originalPost = res.post || res;

      // 1️⃣ đóng modal hiện tại
      setIsPostDetailOpen(false);

      // 2️⃣ mở modal mới với bài gốc
      requestAnimationFrame(() => {
        setActivePost(originalPost);
        setIsPostDetailOpen(true);
      });
    } catch (err) {
      console.error("Không lấy được bài viết gốc", err);
    }
  };

  return (
    <>
      <div className="headerSide">
        <div className="header-left">
          <img className="logoImage" src={logo} alt="logo" />
        </div>

        <div className="header-center">
          <div className="search-bar">
            <SearchIcon onClick={handleSearch} style={{ cursor: "pointer" }} />
            <input
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search"
            />
          </div>
        </div>

        <div className="header-right">
          <button
            className="meeting-btn-header"
            onClick={() => {
              const token = localStorage.getItem("token");

              window.open(
                `http://localhost:3000/channel.html?token=${token}`,
                "_blank",
              );
            }}
          >
            <VideoCameraFrontIcon />
          </button>

          <button
            className="message-btn-header"
            onClick={() => setOpenMessage(true)}
          >
            <ForumIcon />

            {/* ✅ Chỉ hiển thị khi load xong và có tin mới */}
            {!loading && unreadCount > 0 && (
              <span className="chat-badge-header">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {/* ====== CHAT BOX ====== */}
          {openMessage && (
            <div ref={boxRef} className="chat-fixed">
              <ChatDialog
                list={list || []}
                refetch={refetch}
                onClose={() => setOpenMessage(false)}
              />
            </div>
          )}
          <div
            className="rightSide-postInfo"
            onClick={() => navigate(`/profile/${currentUserEmail}`)}
          >
            <img
              className="rightSide-postInfoImg"
              src={currentUser?.avatar}
              alt="avatar"
            />
            <div className="">{currentUser?.fullName}</div>
          </div>

          <div
            className="notification"
            onClick={() => setOpenNotification(true)}
          >
            <NotificationsNoneIcon />
          </div>
        </div>
      </div>

      {/* 🔔 NOTIFICATION MODAL */}
      <NotificationModal
        isOpen={openNotification}
        onClose={() => setOpenNotification(false)}
        onOpenPostDetail={(post, commentId) => {
          setActivePost(post);
          setFocusCommentId(commentId || null);
          setIsPostDetailOpen(true);
        }}
      />

      {isPostDetailOpen && activePost && (
        <PostDetail
          activePost={activePost}
          focusCommentId={focusCommentId}
          onClose={() => setIsPostDetailOpen(false)}
          onCommentAdded={refreshPost}
          onOpenOriginalPost={openOriginalPost}
        />
      )}
    </>
  );
};

export default HeaderSide;
