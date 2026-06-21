import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import "./listRelationship.css";
import AccountService from "../../../../services/AccountService";
import type { GetRelationResponse } from "../../../../services/AccountService";
import { useNavigate } from "react-router-dom";

import { FollowButton } from "../relationship/follow";
import { UnFollowButton } from "../relationship/unfollow";
import { ToastService } from "../../../../services/ToastService";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  profileEmail: string;
  myEmail: string;
  initialTab?: number; // Prop mới để chọn tab mặc định
};

type UserItem = {
  email: string;
  fullName: string;
  avatar?: string;
};

const RelationshipModal: React.FC<Props> = ({
  isOpen,
  onClose,
  profileEmail,
  myEmail,
  initialTab = 0,
}) => {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [loading, setLoading] = useState(false);
  const [followers, setFollowers] = useState<UserItem[]>([]);
  const [followed, setFollowed] = useState<UserItem[]>([]);
  const [blocked, setBlocked] = useState<UserItem[]>([]);
  const [myFollowedEmails, setMyFollowedEmails] = useState<string[]>([]);

  const navigate = useNavigate();

  // Đồng bộ activeTab khi initialTab thay đổi (quan trọng khi chuyển giữa Follow/Followed)
  useEffect(() => {
    if (isOpen) {
      if (myEmail !== profileEmail && initialTab === 2) {
        setActiveTab(0);
      } else {
        setActiveTab(initialTab);
      }
    }
  }, [isOpen, initialTab, myEmail, profileEmail]);

  const loadUsers = async (
    emails: string[],
    setState: React.Dispatch<React.SetStateAction<UserItem[]>>
  ) => {
    const users = await Promise.all(
      emails.map(async (email) => {
        const info = await AccountService.get_account_info(email);
        return {
          email,
          fullName: info.fullName,
          avatar: info.avatar,
        };
      })
    );

    // lọc duy nhất theo email
    const uniqueUsersMap = new Map<string, UserItem>();
    users.forEach((u) => uniqueUsersMap.set(u.email, u));
    setState(Array.from(uniqueUsersMap.values()));
  };

  const reloadRelations = async () => {
    try {
      const relation: GetRelationResponse =
        await AccountService.get_account_relation(profileEmail);
      
      if (myEmail === profileEmail) {
        setMyFollowedEmails(relation.followed ?? []);
      } else {
        const myRelation: GetRelationResponse =
          await AccountService.get_account_relation(myEmail);
        setMyFollowedEmails(myRelation.followed ?? []);
      }

      await Promise.all([
        loadUsers(relation.followers ?? [], setFollowers),
        loadUsers(relation.followed ?? [], setFollowed),
        loadUsers(relation.blocks ?? [], setBlocked),
      ]);
    } catch (err) {
      console.error("Lỗi tải quan hệ:", err);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    reloadRelations().finally(() => setLoading(false));
  }, [isOpen, myEmail, profileEmail]);

  const getUsers = () => {
    if (activeTab === 0) return followers;
    if (activeTab === 1) return followed;
    return blocked;
  };

  const goToProfile = (email: string) => {
    navigate(`/profile/${email}`);
    onClose();
  };

  if (!isOpen) return null;

  const tabs = myEmail === profileEmail
    ? ["Người theo dõi", "Đang theo dõi", "Chặn"]
    : ["Người theo dõi", "Đang theo dõi"];

  return ReactDOM.createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-tabs">
          {tabs.map((tab, index) => (
            <div
              key={index}
              className={`tab ${activeTab === index ? "active" : ""}`}
              onClick={() => setActiveTab(index)}
            >
              {tab}
            </div>
          ))}
        </div>

        <div className="tab-content">
          {loading ? (
            <p className="loading">Đang tải...</p>
          ) : (
            getUsers().map((user) => (
              <div key={user.email} className="user-card">
                <div className="user-info">
                  <img
                    src={user.avatar || "/default-avatar.png"}
                    className="user-avatar"
                    alt={user.fullName}
                    style={{ cursor: "pointer" }}
                    onClick={() => goToProfile(user.email)}
                  />
                  <div
                    className="user-text"
                    onClick={() => goToProfile(user.email)}
                  >
                    <h4>
                      {user.fullName.length > 42
                        ? `${user.fullName.substring(0, 42)}...`
                        : user.fullName}
                    </h4>
                  </div>
                </div>

                <div className="action-btn-wrapper">
                  {activeTab === 0 && (
                    myEmail === user.email ? null : (
                      myFollowedEmails.includes(user.email) ? (
                        <UnFollowButton
                          ownerEmail={myEmail}
                          clientEmail={user.email}
                          onUnFollowSuccess={reloadRelations}
                        />
                      ) : (
                        <FollowButton
                          ownerEmail={myEmail}
                          clientEmail={user.email}
                          onFollowSuccess={reloadRelations}
                        />
                      )
                    )
                  )}

                  {activeTab === 1 && (
                    myEmail === user.email ? null : (
                      myFollowedEmails.includes(user.email) ? (
                        <UnFollowButton
                          ownerEmail={myEmail}
                          clientEmail={user.email}
                          onUnFollowSuccess={reloadRelations}
                        />
                      ) : (
                        <FollowButton
                          ownerEmail={myEmail}
                          clientEmail={user.email}
                          onFollowSuccess={reloadRelations}
                        />
                      )
                    )
                  )}
                  {activeTab === 2 && myEmail === profileEmail && (
                    <button
                      className="btn-message"
                      onClick={async () => {
                        try {
                          await AccountService.un_block({
                            owner: myEmail,
                            client: user.email,
                          });

                          ToastService.success("Bỏ chặn thành công");
                          reloadRelations();
                        } catch (error) {
                          console.error("❌ Lỗi bỏ chặn:", error);
                          ToastService.error("Bỏ chặn thất bại");
                        }
                      }}
                    >
                      Bỏ chặn
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default RelationshipModal;
