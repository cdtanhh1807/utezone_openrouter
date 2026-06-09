import React, { useEffect, useState } from "react";
import FavoriteBorderOutlinedIcon from "@mui/icons-material/FavoriteBorderOutlined";
import CommentService from "../../../../services/CommentService";
import FileService from "../../../../services/FileService";
import type {
  CommentReply,
  CommentReact,
} from "../../../../types/CommentReply";
import { jwtDecode } from "jwt-decode";
import ReportModal from "../report/reportModal";
import ApproveModal from "../report/approveModal";
import { useNavigate } from "react-router-dom";

interface ReplyCommentProps {
  postId: string;
  parentId: string;
  userInfoMap: Record<string, { fullName: string; avatar?: string }>;
  refreshTrigger?: number;
  onReplyDeleted?: () => void;
  onReply: (reply: CommentReply) => void;
}

export interface GetCommentReplyRequest {
  postId: string;
  parentId: string;
}

const isDirectMediaUrl = (value: string) => {
  return /^(https?:\/\/|blob:|data:)/i.test(value || "");
};

const getOriginalFileName = (value: string) => {
  if (!value) return "File đính kèm";

  let name = value;

  try {
    const clean = value.split("?")[0];
    name = clean.split("/").pop() || clean;
    name = decodeURIComponent(name);
  } catch {
    name = value;
  }

  // Bỏ UUID prefix do backend thêm vào file_id:
  // 9247d9aa-b210-4736-9de0-82cd75206ccf_chu_ky.png
  // -> chu_ky.png
  return name.replace(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i,
    "",
  );
};

const getFileType = (value: string) => {
  const clean = (value || "").split("?")[0].toLowerCase();

  if (/\.(mp4|webm|mov|avi|mkv)$/i.test(clean)) return "video";

  if (/\.(jpg|jpeg|png|gif|webp|bmp|svg)$/i.test(clean)) return "image";

  return "file";
};

const ReplyAttachment: React.FC<{ fileRef: string }> = ({ fileRef }) => {
  const [displayUrl, setDisplayUrl] = useState<string>(
    isDirectMediaUrl(fileRef) ? fileRef : "",
  );
  const [loading, setLoading] = useState<boolean>(
    !!fileRef && !isDirectMediaUrl(fileRef),
  );

  const fileName = getOriginalFileName(fileRef);
  const fileType = getFileType(fileRef);

  useEffect(() => {
    let cancelled = false;

    const loadUrl = async () => {
      if (!fileRef) return;

      if (isDirectMediaUrl(fileRef)) {
        setDisplayUrl(fileRef);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        const res = await FileService.getFileUrlData(fileRef);

        if (!cancelled) {
          setDisplayUrl(res.url || "");
        }
      } catch (err) {
        console.error("Không thể lấy URL file reply:", fileRef, err);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadUrl();

    return () => {
      cancelled = true;
    };
  }, [fileRef]);

  if (loading && !displayUrl) {
    return (
      <div className="comment-file-preview">
        📎 <span>{fileName}</span>
        <span style={{ marginLeft: 6, color: "#777" }}>Đang tải...</span>
      </div>
    );
  }

  if (!displayUrl) {
    return (
      <div className="comment-file-preview">
        📎 <span>{fileName}</span>
        <span style={{ marginLeft: 6, color: "#d32f2f" }}>
          Không tải được file
        </span>
      </div>
    );
  }

  if (fileType === "video") {
    return (
      <div className="comment-attachment-item">
        <video src={displayUrl} className="comment-thumbnail-img" controls />
        <div className="comment-attachment-name">{fileName}</div>
      </div>
    );
  }

  if (fileType === "image") {
    return (
      <div className="comment-attachment-item">
        <img
          src={displayUrl}
          alt={fileName}
          className="comment-thumbnail-img"
        />
        <div className="comment-attachment-name">{fileName}</div>
      </div>
    );
  }

  return (
    <a
      href={displayUrl}
      target="_blank"
      rel="noreferrer"
      className="comment-file-preview"
    >
      📄 <span>{fileName}</span>
    </a>
  );
};

export default function ReplyComment({
  postId,
  parentId,
  userInfoMap,
  refreshTrigger,
  onReply,
  onReplyDeleted,
}: ReplyCommentProps) {
  const [replies, setReplies] = useState<CommentReply[]>([]);
  const [loading, setLoading] = useState(true);
  const [openMenu, setOpenMenu] = useState<Record<string, boolean>>({});
  const [popoverMap, setPopoverMap] = useState<Record<string, boolean>>({});
  const [userReactMap, setUserReactMap] = useState<Record<string, string>>({});
  const [reportReply, setReportReply] = useState<CommentReply | null>(null);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [selectedReplyComment, setSelectedReplyComment] =
    useState<CommentReply | null>(null);

  const [isApproveOpen, setIsApproveOpen] = useState(false);

  const token = localStorage.getItem("token");
  let currentUserEmail: string | null = null;
  let currentUserRole: string | null = null;

  if (!currentUserEmail && token) {
    try {
      interface JwtPayload {
        sub: string;
        exp: number;
        per: string;
        role: string;
      }
      const decoded: JwtPayload = jwtDecode<JwtPayload>(token);
      currentUserEmail = decoded.sub;
      currentUserRole = decoded.role;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }

  const fetchReplies = async () => {
    try {
      setLoading(true);
      const data: GetCommentReplyRequest = { postId, parentId };
      const res = await CommentService.getCommentReply(data);

      const list = Array.isArray(res.commentReplys) ? res.commentReplys : [];
      list.sort((a: CommentReply, b: CommentReply) =>
        a.path.localeCompare(b.path),
      );

      setReplies(list);

      if (currentUserEmail) {
        const map: Record<string, string> = {};
        list.forEach((r: CommentReply) => {
          for (const [type, users] of Object.entries(r.react || {})) {
            if ((users as string[]).includes(currentUserEmail!)) {
              map[r.commentId] = type;
            }
          }
        });
        setUserReactMap(map);
      }
    } catch (err) {
      console.error("Lỗi khi lấy reply:", err);
      setReplies([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReplies();
  }, [postId, parentId, refreshTrigger]);

  const normalizeReact = (react: Record<string, string[]>): CommentReact => ({
    love: react.love || [],
    like: react.like || [],
    haha: react.haha || [],
    wow: react.wow || [],
    sad: react.sad || [],
    angry: react.angry || [],
  });

  const handleReplyReact = async (
    commentId: string,
    type: "love" | "like" | "haha" | "wow" | "sad" | "angry",
  ) => {
    try {
      if (!currentUserEmail) return;

      const res = await CommentService.updateCommentReplyReact(
        postId,
        commentId,
        type,
      );

      const updatedReact = normalizeReact(res.react);

      setReplies((prev) =>
        prev.map((r) =>
          r.commentId === commentId ? { ...r, react: updatedReact } : r,
        ),
      );

      const entry = Object.entries(updatedReact).find(([_, users]) =>
        users.includes(currentUserEmail!),
      );
      setUserReactMap((prev) => ({
        ...prev,
        [commentId]: entry ? entry[0] : "",
      }));
    } catch (err) {
      console.error("❌ Lỗi khi gửi reaction cho reply:", err);
    }
  };

  const handleDeleteReply = async (reply: CommentReply) => {
    try {
      await CommentService.updateStatusCommentReply({
        postId: postId,
        commentId: reply.commentId,
        path: reply.path,
        status: "hidden",
      });

      setReplies((prev) => prev.filter((r) => r.commentId !== reply.commentId));
      onReplyDeleted?.();
    } catch (err) {
      console.error("❌ Lỗi khi ẩn reply:", err);
    }
  };

  useEffect(() => {
    const handleClickOutside = () => setOpenMenu({});
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const btnStyle: React.CSSProperties = {
    padding: "6px 12px",
    background: "none",
    border: "none",
    cursor: "pointer",
    width: "100%",
    textAlign: "left",
  };

  const btnStyleDanger: React.CSSProperties = {
    ...btnStyle,
    color: "#e53935",
  };

  const renderContentWithTags = (text: string) => {
    const regex = /(@[^#]+#)/g;
    const parts = text.split(regex);

    return parts.map((part, index) => {
      if (part.startsWith("@") && part.endsWith("#")) {
        const cleanTag = part.slice(0, -1);
        return (
          <span key={index} className="tag-user">
            {cleanTag}
          </span>
        );
      }
      return (
        <span key={index} style={{ color: "#000" }}>
          {part}
        </span>
      );
    });
  };

  const handleRemoveReplyComment = (reply: CommentReply) => {
    setOpenMenu({});

    requestAnimationFrame(() => {
      setSelectedReplyComment(reply);
      setIsApproveOpen(true);
    });
  };

  const navigate = useNavigate();
  const goToProfile = (email: string) => {
    navigate(`/profile/${email}`);
  };

  function formatTimeVN(dateString: string) {
    const utcDate = new Date(dateString + "Z");

    const vnDate = new Date(utcDate.getTime() + 7 * 60 * 60 * 1000);
    const nowVN = new Date(Date.now() + 7 * 60 * 60 * 1000);

    const diffMs = nowVN.getTime() - vnDate.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMinutes < 1) return "vừa xong";
    if (diffMinutes < 60) return `${diffMinutes} phút trước`;
    if (diffHours < 24) return `${diffHours} giờ trước`;
    if (diffDays < 3) return `${diffDays} ngày trước`;

    return vnDate.toLocaleString("vi-VN");
  }

  if (loading) return <div>Đang tải reply...</div>;

  return (
    <div className="reply-list">
      {replies.map((reply: CommentReply) => {
        const level = reply.path?.split(";").length || 1;
        return (
          <div
            key={reply.commentId}
            id={`comment-${reply.commentId}`}
            className="comment-card"
            style={{ marginLeft: (level - 1) * 16 + (level - 1) * 16 }}
          >
            <img
              src={userInfoMap[reply.commentBy]?.avatar}
              alt="avatar"
              className="comment-avatar"
              style={{ cursor: "pointer" }}
              onClick={() => goToProfile(reply.commentBy)}
            />

            <div className="comment-body">
              <div
                className="comment-header"
                onClick={() => goToProfile(reply.commentBy)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  cursor: "pointer",
                }}
              >
                <div>
                  <span className="comment-username">
                    {userInfoMap[reply.commentBy]?.fullName || reply.commentBy}
                  </span>
                  <span className="comment-time">
                    {formatTimeVN(reply.createdAt)}
                  </span>
                </div>

                <div
                  className="comment-options"
                  style={{ position: "relative" }}
                >
                  <button
                    type="button"
                    className="options-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenu((prev) => ({
                        ...prev,
                        [reply.commentId]: !prev[reply.commentId],
                      }));
                    }}
                  >
                    ⋮
                  </button>

                  {openMenu[reply.commentId] && (
                    <div
                      className="comment-menu"
                      style={{
                        position: "absolute",
                        top: "24px",
                        right: 0,
                        background: "#fff",
                        border: "1px solid #ccc",
                        borderRadius: "6px",
                        zIndex: 1000,
                        boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
                        minWidth: "170px",
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {currentUserRole === "Moderator" &&
                        currentUserEmail !== reply.commentBy && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRemoveReplyComment(reply);
                            }}
                            style={btnStyleDanger}
                          >
                            🛡️ Gỡ bình luận
                          </button>
                        )}

                      {reply.commentBy === currentUserEmail ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteReply(reply);
                            setOpenMenu({});
                          }}
                          style={btnStyleDanger}
                        >
                          ❌ Xóa bình luận
                        </button>
                      ) : (
                        currentUserRole !== "Moderator" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setReportReply(reply);
                              setReportModalOpen(true);
                              setOpenMenu({});
                            }}
                            style={btnStyle}
                          >
                            🚩 Báo cáo bình luận
                          </button>
                        )
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="comment-content">
                {renderContentWithTags(reply.content)}
              </div>

              {reply.thumbnails && reply.thumbnails.length > 0 && (
                <div className="comment-thumbnail">
                  {reply.thumbnails.map((fileRef: string, index: number) => (
                    <ReplyAttachment
                      key={`${reply.commentId}-${fileRef}-${index}`}
                      fileRef={fileRef}
                    />
                  ))}
                </div>
              )}

              <div className="comment-reacts">
                <div
                  className="like-container"
                  onMouseEnter={() =>
                    setPopoverMap((prev) => ({
                      ...prev,
                      [reply.commentId]: true,
                    }))
                  }
                  onMouseLeave={() =>
                    setPopoverMap((prev) => ({
                      ...prev,
                      [reply.commentId]: false,
                    }))
                  }
                >
                  <button
                    type="button"
                    className={`react-btn ${
                      userReactMap[reply.commentId]
                        ? `active-${userReactMap[reply.commentId]}`
                        : ""
                    }`}
                    onClick={() => handleReplyReact(reply.commentId, "love")}
                  >
                    {userReactMap[reply.commentId] === "love" ? (
                      "❤️"
                    ) : userReactMap[reply.commentId] === "like" ? (
                      "👍"
                    ) : userReactMap[reply.commentId] === "haha" ? (
                      "😂"
                    ) : userReactMap[reply.commentId] === "wow" ? (
                      "😮"
                    ) : userReactMap[reply.commentId] === "sad" ? (
                      "😢"
                    ) : userReactMap[reply.commentId] === "angry" ? (
                      "😡"
                    ) : (
                      <FavoriteBorderOutlinedIcon />
                    )}
                  </button>

                  {popoverMap[reply.commentId] && (
                    <div className="emote-popover">
                      {["love", "like", "haha", "wow", "sad", "angry"].map(
                        (e) => {
                          const emojiMap: Record<string, string> = {
                            love: "❤️",
                            like: "👍",
                            haha: "😂",
                            wow: "😮",
                            sad: "😢",
                            angry: "😡",
                          };
                          return (
                            <span
                              key={e}
                              onClick={() =>
                                handleReplyReact(
                                  reply.commentId,
                                  e as
                                    | "love"
                                    | "like"
                                    | "haha"
                                    | "wow"
                                    | "sad"
                                    | "angry",
                                )
                              }
                            >
                              {emojiMap[e]}
                            </span>
                          );
                        },
                      )}
                    </div>
                  )}
                </div>

                {Object.values(reply.react || {}).reduce(
                  (s, arr) => s + arr.length,
                  0,
                ) > 0 && (
                  <label className="countReact-Comment">
                    {Object.values(reply.react || {}).reduce(
                      (s, arr) => s + arr.length,
                      0,
                    )}{" "}
                    lượt bày tỏ cảm xúc
                  </label>
                )}

                <button
                  type="button"
                  className="reply-btn"
                  onClick={() => onReply(reply)}
                >
                  Trả lời
                </button>
              </div>
            </div>
          </div>
        );
      })}

      {reportReply && reportModalOpen && (
        <ReportModal
          isOpen={reportModalOpen}
          onClose={() => {
            setReportModalOpen(false);
            setReportReply(null);
          }}
          policy_type="bình luận"
          type="comment"
          content={reportReply.content}
          contentId={reportReply.commentId}
          contentParentId={postId}
          violatorEmail={reportReply.commentBy}
          path={reportReply.path}
        />
      )}

      {selectedReplyComment && (
        <ApproveModal
          isOpen={isApproveOpen}
          onClose={() => setIsApproveOpen(false)}
          policy_element="bình luận"
          element="comment"
          elementId={selectedReplyComment.commentId}
          elementParentId={postId}
          currentUserEmail={currentUserEmail ?? ""}
          comment={selectedReplyComment}
          onRemoved={() => {
            setReplies((prev) =>
              prev.filter(
                (r) => r.commentId !== selectedReplyComment.commentId,
              ),
            );
            onReplyDeleted?.();
          }}
        />
      )}
    </div>
  );
}
