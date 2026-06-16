import "./profileHeader.css";
import { useRef, useEffect, useState } from "react";
import { jwtDecode } from "jwt-decode";
import AccountService from "../../../../services/AccountService";
import type { UserInfo } from "../../../../types/Account";
import EditProfileModal from "./editProfileModal";
import { FollowButton } from "../relationship/follow";
import { UnFollowButton } from "../relationship/unfollow";
import type { Post } from "../../../../types/Post";
import { postAPI } from "../../../../services/PostService";
import EditIcon from "@mui/icons-material/Edit";
import { messageAPI } from "../chat/messageService";
import ChatDialog from "../chat/ChatDialog";
import useConversations from "../chat/useConversation";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import ReportModal from "../report/reportModal";
import { useNavigate } from "react-router-dom";
import { ToastService } from "../../../../services/ToastService";
import SendIcon from '@mui/icons-material/Send';
import LocationOnIcon from "@mui/icons-material/LocationOn";
import PhoneIcon from "@mui/icons-material/Phone";
import CakeIcon from "@mui/icons-material/Cake";
import SchoolIcon from "@mui/icons-material/School";

interface ProfileHeaderProps {
  email?: string;
}

const ProfileHeader: React.FC<ProfileHeaderProps> = ({ email }) => {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [posts, setPosts] = useState<Post[]>([]);
  const [openMessage, setOpenMessage] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const [openMenu, setOpenMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [openReportModal, setOpenReportModal] = useState(false);
  const [reportEmail, setReportEmail] = useState<string | null>(null);
  const navigate = useNavigate();
  const { list, refetch } = useConversations();

  let token = localStorage.getItem("token");
  interface JwtPayload {
    sub: string;
    exp: number;
  }
  let decodedEmail: string | null = null;

  if (token) {
    try {
      const decoded: JwtPayload = jwtDecode<JwtPayload>(token);
      decodedEmail = decoded.sub;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }
  const currentUserEmail: string | null = email || decodedEmail;

  useEffect(() => {
    if (!openMessage) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpenMessage(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openMessage]);

  useEffect(() => {
    const fetchUser = async () => {
      if (!currentUserEmail) {
        console.error("❌ Không có email để fetch thông tin người dùng");
        setLoading(false);
        return;
      }

      try {
        const res = await AccountService.get_account_info(currentUserEmail);
        setUser(res || null);
        let ress;
        ress = await postAPI.getByEmail(currentUserEmail);
        setPosts(ress.post_list || []);
      } catch (err) {
        console.error("❌ Lỗi gọi API account_info:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [currentUserEmail]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenu(false);
      }
    };

    if (openMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openMenu]);

  if (loading) return <div className="loading-state">Đang tải dữ liệu...</div>;
  if (!user) return <div className="error-state">Không tìm thấy thông tin người dùng.</div>;

  const followersCount = user?.followers?.length || 0;
  const followingCount = user?.followed?.length || 0;
  const postsCount = posts?.length || 0;

  const isCurrentUser = decodedEmail === currentUserEmail;
  const hasFollowed = user?.followers?.includes(decodedEmail || "") || false;

  const handleSendMessage = async () => {
    if (!currentUserEmail) return;
    try {
      await messageAPI.send(email!, { content: "Bắt đầu trò chuyện!" });
      console.log("Đã gửi tin nhắn hello");
    } catch (err) {
      console.error("Lỗi gửi tin nhắn:", err);
    }
  };

  const checkConversationExists = async (): Promise<boolean> => {
    if (!decodedEmail || !currentUserEmail) return false;
    try {
      const res = await messageAPI.getConversation(currentUserEmail);
      const messages = res.data || [];
      const myConversationId1 = `${decodedEmail}_${currentUserEmail}`;
      const myConversationId2 = `${currentUserEmail}_${decodedEmail}`;

      return messages.some(
        (m: any) =>
          m.conversation_id === myConversationId1 ||
          m.conversation_id === myConversationId2,
      );
    } catch (err) {
      console.error("❌ Lỗi kiểm tra conversation:", err);
      return false;
    }
  };

  return (
    <div className="modern-profile-container">
      {/* 1. KHU VỰC HEADER CHÍNH (COVER + AVATAR + INFO + STATS) */}
      <div className="modern-header-card">
        {/* Cover Photo Xóa font mặc định thay bằng dải màu gradient sinh động */}
        <div className="profile-cover"></div>

        <div className="profile-core-info">
          {/* Avatar Section */}
          <div className="avatar-wrapper">
            <div className="avatar-ring">
              {user.avatar ? (
                <img className="profile-avatar" src={user.avatar} alt="avatar" />
              ) : (
                <div className="avatar-placeholder"></div>
              )}
            </div>
            {/* Fake Verified Badge */}
            <div className="verified-badge">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" fill="#0866FF"/>
                <path d="M16.5 8.5L10.5 14.5L7.5 11.5" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>

          {/* User Info Section */}
          <div className="user-details-section">
            <h1 className="profile-name">
              {user.fullName}
            </h1>
            <p className="profile-headline">
              {user.department ? `KHOA ${user.department.toUpperCase()}` : "Sinh viên HCMUTE"}
            </p>
            <p className="profile-bio">{user.description || "Chưa cập nhật tiểu sử."}</p>
          </div>

          {/* Action Buttons Section */}
          <div className="profile-actions-wrapper">
            {isCurrentUser ? (
              <button
                className="btn-modern btn-edit-profile"
                onClick={() => setIsModalOpen(true)}
              >
                <EditIcon sx={{ fontSize: 18 }} /> Chỉnh sửa hồ sơ
              </button>
            ) : (
              <div className="action-buttons-group">
                {hasFollowed ? (
                  <UnFollowButton
                    ownerEmail={decodedEmail || ""}
                    clientEmail={currentUserEmail || ""}
                    onUnFollowSuccess={() => {
                      setUser((prev) =>
                        prev
                          ? {
                              ...prev,
                              followers: (prev.followers ?? []).filter(
                                (f) => f !== decodedEmail,
                              ),
                            }
                          : prev,
                      );
                    }}
                  />
                ) : (
                  <FollowButton
                    ownerEmail={decodedEmail || ""}
                    clientEmail={currentUserEmail || ""}
                    onFollowSuccess={() => {
                      setUser((prev) =>
                        prev
                          ? {
                              ...prev,
                              followers: [
                                ...(prev.followers ?? []),
                                decodedEmail || "",
                              ],
                            }
                          : prev,
                      );
                    }}
                  />
                )}
                
                <button
                  className="btn-modern btn-message"
                  onClick={async () => {
                    const exists = await checkConversationExists();
                    if (!exists) {
                      await handleSendMessage();
                    }
                    await refetch();
                    setOpenMessage(true);
                  }}
                >
                  <SendIcon sx={{ fontSize: 18 }} />
                  Nhắn tin
                </button>

                <div className="menu-dot-wrapper">
                  <button
                    className="btn-modern dot-btn-message"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenu((prev) => !prev);
                    }}
                  >
                    <MoreHorizIcon />
                  </button>

                  {openMenu && (
                    <div ref={menuRef} className="account-menu glass-panel">
                      <div
                        className="menu-item"
                        onClick={() => {
                          setOpenMenu(false);
                          setReportEmail(currentUserEmail);
                          setOpenReportModal(true);
                        }}
                      >
                        🚩 Báo cáo tài khoản
                      </div>
                      <div
                        className="menu-item danger"
                        onClick={() => {
                          setOpenMenu(false);
                          ToastService.confirm(
                            "Bạn chắc chắn muốn chặn tài khoản này?",
                            async () => {
                              try {
                                await AccountService.block({
                                  owner: decodedEmail!,
                                  client: currentUserEmail!,
                                });
                                ToastService.success("Chặn thành công");
                                navigate("/home");
                              } catch (error) {
                                console.error("❌ Lỗi chặn tài khoản:", error);
                                ToastService.error("Chặn thất bại");
                              }
                            },
                            {
                              confirmText: "Chặn",
                              cancelText: "Hủy",
                            },
                          );
                        }}
                      >
                        ⛔ Chặn tài khoản
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Profile Statistics (Dạng tab chuyển đổi như mockup) */}
        <div className="profile-stats-bar">
          <div className="stat-item">
            <span className="stat-label">Người theo dõi</span>
            <span className="stat-value">{followersCount}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Đang theo dõi</span>
            <span className="stat-value">{followingCount}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Bài viết</span>
            <span className="stat-value">{postsCount}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Điểm hoạt động</span>
            <span className="stat-value">N/A</span>
          </div>
        </div>
      </div>

      {/* CÁC MODAL VÀ PORTALS GIỮ NGUYÊN */}
      {isModalOpen && (
        <EditProfileModal user={user} onClose={() => setIsModalOpen(false)} />
      )}
      
      {openMessage && (
        <div ref={boxRef} className="chat-fixed">
          <ChatDialog
            onClose={() => setOpenMessage(false)}
            list={list}
            refetch={refetch}
          />
        </div>
      )}
      
      {openReportModal && reportEmail && (
        <ReportModal
          isOpen={openReportModal}
          onClose={() => {
            setOpenReportModal(false);
            setReportEmail(null);
          }}
          policy_type="tài khoản"
          type="account"
          violatorEmail={reportEmail}
          content=""
        />
      )}
    </div>
  );
};

export default ProfileHeader;