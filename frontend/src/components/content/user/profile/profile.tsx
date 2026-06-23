import "./profile.css";
import { useParams } from "react-router-dom";
import { useState, useRef, useEffect, useMemo } from "react";
import ProfileHeader from "./profileHeader";
import logochat from "../../../../assets/logochat.png";
import ProfilePosts from "./profilePost";
import ProfileArchived from "./profileArchived";
import ProfileAlbum from "./profileAlbum";
import ProfileSaved from "./profileSaved";

// Icons hiện có
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import ArticleIcon from "@mui/icons-material/Article";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import InventoryIcon from "@mui/icons-material/Inventory";
import BookmarkBorderIcon from "@mui/icons-material/BookmarkBorder";
import BookmarkIcon from "@mui/icons-material/Bookmark";
import PhotoLibraryOutlinedIcon from "@mui/icons-material/PhotoLibraryOutlined";
import EventIcon from "@mui/icons-material/Event";

// Icons bổ sung cho thiết kế mới
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import VideoCameraBackOutlinedIcon from "@mui/icons-material/VideoCameraBackOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";

import ChatDialog from "../chat/ChatDialog";
import useConversations from "../chat/useConversation";
import { jwtDecode } from "jwt-decode";
import ProfileCatalog from "./profileCatalog";
import ProfileDetail from "./profileDetail";
import StoryHighlightList from "./StoryHighlightList";
import CreatePost from "../create/createPost";
import { ToastService } from "../../../../services/ToastService";
import AccountService from "../../../../services/AccountService";
import type { UserInfo } from "../../../../types/Account";


function Profile() {
  const { email } = useParams<{ email: string }>();

  const [openMessage, setOpenMessage] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "posts" | "album" | "archived" | "saved" | "catalog"
  >("posts");
  const [openCreatePost, setOpenCreatePost] = useState<boolean>(false);
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [hasHighlights, setHasHighlights] = useState(true);
  const [profileUser, setProfileUser] = useState<UserInfo | null>(null);

  const boxRef = useRef<HTMLDivElement>(null);

  const token = localStorage.getItem("token");
  let currentUserEmail: string | null = null;
  let currentUserRole: string | null = null;

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
      currentUserRole = decoded.role;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }

  const isOwnProfile = !email || email === currentUserEmail;
  const targetEmail = email || currentUserEmail || "";

  useEffect(() => {
    if (!targetEmail) return;
    AccountService.get_account_info(targetEmail)
      .then((res) => {
        setProfileUser(res || null);
      })
      .catch((err) => {
        console.error("❌ Lỗi lấy thông tin profile:", err);
      });
  }, [targetEmail]);

  const isMOR = profileUser?.role === "Moderator";
  const showCatalogTab = isMOR;

  const { list, loading, refetch } = useConversations();

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
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [openMessage]);

  useEffect(() => {
    setActiveTab("posts");
    
    // Reset scroll position to top of the page when transitioning to a different profile
    window.scrollTo({ top: 0 });
    const container = document.querySelector(".main-right-side");
    if (container) {
      container.scrollTo({ top: 0 });
    }
  }, [email]);

  const canCreateContent = () => {
    const token = localStorage.getItem("token");
    if (!token) return false;

    try {
      const decoded: any = jwtDecode(token);
      return decoded.per?.[0] === "1";
    } catch {
      return false;
    }
  };

  return (
    <div className="modern-profile-page">
      <div className="profile-layout-wrapper">
        {/* ===== 1. HEADER ===== */}
        <div className="profile-header-section">
          <ProfileHeader email={email} />
        </div>

        {/* ===== 2. BODY GRID (2 CỘT) ===== */}
        <div className="profile-body-grid">
          {/* --- Cột trái: Sidebar --- */}
          <div className="profile-sidebar-left">
            <ProfileDetail email={email} />
          </div>

          {/* --- Cột phải: Story, Tabs & Main Feed --- */}
          <div className="profile-main-content">
            {/* Tầng 1: Story Block */}
            {(email === undefined || email === currentUserEmail || hasHighlights) && (
              <div className="profile-story-section card-box">
                <div className="story-wrapper-horizontal">
                  <StoryHighlightList 
                    email={email} 
                    onLoadComplete={(count) => setHasHighlights(count > 0)}
                  />
                </div>
              </div>
            )}

            {/* Tầng 2: WIDGET TẠO BÀI VIẾT (SÁNG TẠO - DASHBOARD STYLE) */}
            {activeTab === "posts" && email === currentUserEmail && (
              <div className="modern-compose-widget card-box">
                <div className="compose-prompt-area">
                  {/* <div className="compose-icon-wrapper">
                    <AutoAwesomeOutlinedIcon sx={{ color: '#0866ff' }} />
                  </div> */}
                  <div className="compose-text">
                    <h4 className="compose-title">
                      {email === currentUserEmail
                        ? "Hôm nay có gì mới?"
                        : "Gửi thông điệp"}
                    </h4>
                    <p className="compose-subtitle">
                      {email === currentUserEmail
                        ? "Chia sẻ dự án, tài liệu hoặc một câu hỏi thú vị với cộng đồng HCMUTE."
                        : "Để lại vài lời giao lưu trên tường nhà của sinh viên này..."}
                    </p>
                  </div>
                </div>

                <div className="compose-action-row">
                  <button
                    className="compose-btn btn-main"
                    onClick={(e) => {
                      e.stopPropagation();

                      if (!canCreateContent()) {
                        ToastService.error(
                          "Tài khoản của bạn đã bị cấm đăng tải nội dung",
                        );
                        return;
                      }
                      setStep(0);
                      setOpenCreatePost(true);
                    }}
                  >
                    <EditOutlinedIcon sx={{ fontSize: 18 }} /> Viết bài
                  </button>
                  <button
                    className="compose-btn btn-media"
                    title="Tải ảnh lên"
                    onClick={(e) => {
                      e.stopPropagation();

                      if (!canCreateContent()) {
                        ToastService.error(
                          "Tài khoản của bạn đã bị cấm đăng tải nội dung",
                        );
                        return;
                      }
                      setStep(0);
                      setOpenCreatePost(true);
                    }}
                  >
                    <PhotoLibraryOutlinedIcon sx={{ fontSize: 20 }} />
                  </button>
                  <button
                    className="compose-btn btn-media"
                    title="Thêm video"
                    onClick={(e) => {
                      e.stopPropagation();

                      if (!canCreateContent()) {
                        ToastService.error(
                          "Tài khoản của bạn đã bị cấm đăng tải nội dung",
                        );
                        return;
                      }
                      setStep(0);
                      setOpenCreatePost(true);
                    }}
                  >
                    <VideoCameraBackOutlinedIcon sx={{ fontSize: 20 }} />
                  </button>
                  <button
                    className="compose-btn btn-media"
                    title="Đính kèm tài liệu"
                    onClick={(e) => {
                      e.stopPropagation();

                      if (!canCreateContent()) {
                        ToastService.error(
                          "Tài khoản của bạn đã bị cấm đăng tải nội dung",
                        );
                        return;
                      }
                      setStep(2);
                      setOpenCreatePost(true);
                    }}
                  >
                    <DescriptionOutlinedIcon sx={{ fontSize: 20 }} />
                  </button>
                </div>
              </div>
            )}

            {/* Tầng 3: Thanh Tabs điều hướng */}
            <div className="modern-profile-tabs card-box">
              <button
                className={activeTab === "posts" ? "active" : ""}
                onClick={() => setActiveTab("posts")}
              >
                {activeTab === "posts" ? (
                  <ArticleIcon />
                ) : (
                  <ArticleOutlinedIcon />
                )}
                <span>Bài viết</span>
              </button>

              <button
                className={activeTab === "album" ? "active" : ""}
                onClick={() => setActiveTab("album")}
              >
                <PhotoLibraryOutlinedIcon />
                <span>Ảnh</span>
              </button>

              {email === currentUserEmail && (
                <button
                  className={activeTab === "archived" ? "active" : ""}
                  onClick={() => setActiveTab("archived")}
                >
                  {activeTab === "archived" ? (
                    <InventoryIcon />
                  ) : (
                    <Inventory2OutlinedIcon />
                  )}
                  <span>Thùng rác</span>
                </button>
              )}

              <button
                className={activeTab === "saved" ? "active" : ""}
                onClick={() => setActiveTab("saved")}
              >
                {activeTab === "saved" ? (
                  <BookmarkIcon />
                ) : (
                  <BookmarkBorderIcon />
                )}
                <span>Đã lưu</span>
              </button>

              {showCatalogTab && (
                <button
                  className={activeTab === "catalog" ? "active" : ""}
                  onClick={() => setActiveTab("catalog")}
                >
                  <EventIcon />
                  <span>Sự kiện</span>
                </button>
              )}
            </div>

            {/* Tầng 4: Nội dung Feed hiển thị dựa trên Tab */}
            <div className="feed-content-area">
              {activeTab === "posts" && <ProfilePosts email={email || currentUserEmail || undefined} />}
              {activeTab === "album" && <ProfileAlbum email={email || currentUserEmail || undefined} />}
              {activeTab === "archived" && <ProfileArchived />}
              {activeTab === "saved" && <ProfileSaved email={email || currentUserEmail || undefined} />}
              {activeTab === "catalog" && showCatalogTab && (
                <ProfileCatalog email={targetEmail || undefined} isOwnProfile={isOwnProfile} />
              )}
            </div>
          </div>
        </div>
      </div>
      <CreatePost
        isOpen={openCreatePost}
        onClose={() => setOpenCreatePost(false)}
        initialStep={step}
        onPostSaved={() => window.location.reload()}
      />
    </div>
  );
}

export default Profile;
