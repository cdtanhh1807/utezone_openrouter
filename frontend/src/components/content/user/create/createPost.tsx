import "./createPost.css";
import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useRef } from "react";
import { postAPI } from "../../../../services/PostService";
import FileService, {
  type UploadResponse,
} from "../../../../services/FileService";
import type { Post } from "../../../../types/Post";
import FilterOutlinedIcon from "@mui/icons-material/FilterOutlined";
import ChevronLeftOutlinedIcon from "@mui/icons-material/ChevronLeftOutlined";
import ChevronRightOutlinedIcon from "@mui/icons-material/ChevronRightOutlined";
import { jwtDecode } from "jwt-decode";
import AccountService from "../../../../services/AccountService";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";
import ArrowBackIosIcon from "@mui/icons-material/ArrowBackIos";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import PublicIcon from "@mui/icons-material/Public";
import SecurityIcon from "@mui/icons-material/Security";
import BookmarkIcon from "@mui/icons-material/Bookmark";
import DepartmentMultiSelect from "./departmentSelect";
import { ToastService } from "../../../../services/ToastService";
import { useAIModerationStore } from "../stores/aiModerationStore";
import { useMention } from "../post/useMention"; // sửa path cho đúng
import { useAIStore } from "../stores/aiStore";

interface CreatePostProps {
  isOpen: boolean;
  onClose: () => void;
  editingPost?: Post | null;
  onPostSaved?: () => void;
}

const backdrop = { hidden: { opacity: 0 }, visible: { opacity: 1 } };
const modal = {
  hidden: { opacity: 0, scale: 0.8, y: 50 },
  visible: { opacity: 1, scale: 1, y: 0 },
};

const CreatePost = ({
  isOpen,
  onClose,
  editingPost,
  onPostSaved,
}: CreatePostProps) => {
  const [step, setStep] = useState<0 | 1 | 2 | 3>(0);
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [layout, setLayout] = useState<"overlay" | "grid">("overlay");
  const [loading, setLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [visibility, setVisibility] = useState<"public" | "follow" | "private">(
    "public",
  );
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>([]);
  const setModerating = useAIModerationStore((state) => state.setModerating);
  const { setStatus } = useAIStore();

  const contentRef = useRef<HTMLTextAreaElement>(null);

  const visibilityText = {
    public: "Công khai",
    follow: "Người theo dõi",
    private: "Chỉ mình tôi",
  };

  const visibilityIcon = {
    public: <PublicIcon />,
    follow: <BookmarkIcon />,
    private: <SecurityIcon />,
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      const decoded: any = jwtDecode(token);
      AccountService.get_account_info(decoded.sub).then(setCurrentUser);
    } catch (err) {
      console.error("❌ Token lỗi", err);
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (editingPost) {
      setContent(editingPost.content || "");
      setPreviews(editingPost.thumbnails_url || []);
      setFiles([]);
    } else {
      setContent("");
      setPreviews([]);
      setFiles([]);
    }
    setCurrentIndex(0);
    setStep(0);
  }, [editingPost]);

  const isVideo = (url: string) => {
    // blob URL (file mới chọn) → kiểm tra bằng mime type ở chỗ khác
    if (url.startsWith("blob:")) return false;

    return /\.(mp4|mov|mkv|avi|webm)$/i.test(url);
  };

  useEffect(() => {
    const textarea = contentRef.current;
    const highlight = document.querySelector(
      ".compose-highlight",
    ) as HTMLElement;

    if (!textarea || !highlight) return;

    const syncScroll = () => {
      highlight.scrollTop = textarea.scrollTop;
    };

    textarea.addEventListener("scroll", syncScroll);

    return () => {
      textarea.removeEventListener("scroll", syncScroll);
    };
  }, []);

  const handleBack = () => {
    if (step === 0) {
      onClose();
      return;
    }
    if (step === 1) {
      setStep(0);
      return;
    }
    if (step === 2) {
      previews.length === 0 ? setStep(0) : setStep(1);
      return;
    }
    if (step === 3) setStep(2);
  };

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (!selectedFiles.length) return;

    const newPreviews = selectedFiles.map((f) => URL.createObjectURL(f));

    setFiles((prev) => [...prev, ...selectedFiles]);
    setPreviews((prev) => [...prev, ...newPreviews]);
    setCurrentIndex(previews.length);

    if (step === 0 || step === 2) setStep(1);
  };

  const handlePost = async () => {
    onClose();

    const hasMedia = previews.length > 0 || attachments.length > 0;

    const hasTitle = title.trim().length > 0;

    const hasContent = content.trim().length > 0;

    if (!hasMedia && !hasTitle && !hasContent) {
      ToastService.warning("Vui lòng thêm nội dung hoặc hình ảnh để đăng bài.");

      return;
    }

    setLoading(true);

    try {
      // 🔥 AI bắt đầu moderation
      setStatus("moderating");

      let fileIds: string[] = [];

      const allFiles = [...files, ...attachments];

      if (allFiles.length) {
        const uploads = await Promise.all(
          allFiles.map(FileService.uploadPicture),
        );

        fileIds = uploads.map((u) => u.file_id);
      }

      await postAPI.addPost({
        title,
        content,
        thumbnails: fileIds,
        visibility,
        layout,

        category: selectedDepartments.length === 0 ? [] : selectedDepartments,

        postType: "short",

        status: "active",

        pollData: null,
      });

      // reset
      setFiles([]);
      setAttachments([]);
      setPreviews([]);

      onClose();

      onPostSaved?.();

      // 🔥 moderation success
      setStatus("success");

      ToastService.success("Đăng bài thành công!");

      setTimeout(() => {
        setStatus("idle");
      }, 2500);
    } catch (err) {
      setStatus("idle");

      ToastService.error("Đăng bài thất bại, vui lòng thử lại.");
    }

    setLoading(false);
  };

  const handleAttachmentUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    if (!selected.length) return;

    setAttachments((prev) => [...prev, ...selected]);
  };
  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleNext = () => {
    if (step === 0) {
      setStep(previews.length > 0 ? 1 : 2);
      return;
    }

    if (step === 1) {
      setStep(2);
      return;
    }
  };

  useEffect(() => {
    if (step === 1 && previews.length === 0) {
      setStep(0);
    }
  }, [previews.length, step]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div className="modal-backdrop" onClick={onClose}>
          <motion.div
            className="cp-modal-container"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="step-nav">
              <button className="next-step" onClick={handleBack}>
                {step !== 0 && <ArrowBackIosIcon />}
              </button>

              <h4>Tạo bài viết</h4>

              {step < 2 ? (
                <button className="next-step" onClick={handleNext}>
                  <ArrowForwardIosIcon />
                </button>
              ) : (
                <button
                  className="cp-post-btn"
                  onClick={handlePost}
                  disabled={loading}
                >
                  {loading ? "Đang đăng..." : "Đăng"}
                </button>
              )}
            </div>

            {/* Step 0: icon */}
            {step === 0 && (
              <div className="step-icon">
                <FilterOutlinedIcon style={{ fontSize: 100 }} />
                <label className="upload-center">
                  Chọn ảnh hoặc video
                  <input
                    type="file"
                    accept="image/*,video/*,audio/mpeg"
                    multiple
                    onChange={handleUpload}
                  />
                </label>
              </div>
            )}

            {/* Step 1: upload */}
            {step === 1 && previews.length > 0 && (
              <div className="cp-preview-wrapper">
                <div className="cp-carousel-container">
                  {files[currentIndex] ? (
                    files[currentIndex].type.startsWith("video/") ? (
                      <video controls className="preview-video">
                        <source
                          src={URL.createObjectURL(files[currentIndex])}
                        />
                      </video>
                    ) : (
                      <img
                        src={URL.createObjectURL(files[currentIndex])}
                        className="preview-image"
                      />
                    )
                  ) : isVideo(previews[currentIndex]) ? (
                    <video controls className="preview-video">
                      <source src={previews[currentIndex]} />
                    </video>
                  ) : (
                    <img
                      src={previews[currentIndex]}
                      className="preview-image"
                    />
                  )}

                  <ChevronLeftOutlinedIcon
                    className="nav-left"
                    onClick={() =>
                      setCurrentIndex(
                        (currentIndex - 1 + previews.length) % previews.length,
                      )
                    }
                  />
                  <ChevronRightOutlinedIcon
                    className="nav-right"
                    onClick={() =>
                      setCurrentIndex((currentIndex + 1) % previews.length)
                    }
                  />
                </div>

                <div className="cp-thumbnail-bar">
                  {previews.map((url, idx) => {
                    const previewUrl = files[idx]
                      ? URL.createObjectURL(files[idx])
                      : url;

                    const isVideoFile = files[idx]
                      ? files[idx].type.startsWith("video/")
                      : isVideo(url);

                    return (
                      <div key={idx} className="thumb-wrapper">
                        {isVideoFile ? (
                          <video
                            src={previewUrl}
                            className={`thumbnail ${
                              idx === currentIndex ? "active-thumb" : ""
                            }`}
                            onClick={() => setCurrentIndex(idx)}
                            muted
                          />
                        ) : (
                          <img
                            src={previewUrl}
                            alt="thumb"
                            className={`thumbnail ${
                              idx === currentIndex ? "active-thumb" : ""
                            }`}
                            onClick={() => setCurrentIndex(idx)}
                          />
                        )}

                        {/* Nút xoá */}
                        <span
                          className="delete-thumb"
                          onClick={(e) => {
                            e.stopPropagation();

                            setFiles((prev) =>
                              prev.filter((_, i) => i !== idx),
                            );

                            setPreviews((prev) =>
                              prev.filter((_, i) => i !== idx),
                            );

                            setCurrentIndex((prev) =>
                              Math.max(0, Math.min(prev, previews.length - 2)),
                            );
                          }}
                        >
                          ✕
                        </span>
                      </div>
                    );
                  })}

                  {/* Thumbnail + để upload thêm */}
                  <label className="thumbnail add-thumb">
                    +
                    <input
                      type="file"
                      accept="image/*,video/*"
                      multiple
                      onChange={handleUpload}
                    />
                  </label>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="compose-layout">
                {/* LEFT: IMAGE SLIDER */}
                {/* LEFT: IMAGE / PLACEHOLDER */}
                <div className="compose-left">
                  {previews.length > 0 ? (
                    /* ===== CÓ ẢNH ===== */
                    <div className="compose-slider">
                      {files[currentIndex]?.type.startsWith("video/") ||
                      isVideo(previews[currentIndex]) ? (
                        <video controls className="compose-media">
                          <source
                            src={
                              files[currentIndex]
                                ? URL.createObjectURL(files[currentIndex])
                                : previews[currentIndex]
                            }
                          />
                        </video>
                      ) : (
                        <img
                          src={
                            files[currentIndex]
                              ? URL.createObjectURL(files[currentIndex])
                              : previews[currentIndex]
                          }
                          className="compose-media"
                        />
                      )}

                      {currentIndex > 0 && (
                        <ChevronLeftOutlinedIcon
                          className="compose-nav-left"
                          onClick={() => setCurrentIndex((prev) => prev - 1)}
                        />
                      )}

                      {currentIndex < previews.length - 1 && (
                        <ChevronRightOutlinedIcon
                          className="compose-nav-right"
                          onClick={() => setCurrentIndex((prev) => prev + 1)}
                        />
                      )}
                    </div>
                  ) : (
                    /* ===== KHÔNG CÓ ẢNH ===== */
                    <div className="compose-placeholder">
                      <label className="upload-center">
                        Thêm ảnh hoặc video
                        <input
                          type="file"
                          accept="image/*,video/*"
                          multiple
                          onChange={handleUpload}
                        />
                      </label>
                    </div>
                  )}
                </div>

                {/* RIGHT: INFO + CONTENT */}
                <div className="compose-right">
                  <div className="compose-postInfo">
                    <img className="compose-avatar" src={currentUser?.avatar} />
                    <div className="compose-user">
                      <div className="compose-name">
                        {currentUser?.fullName}
                      </div>
                    </div>
                  </div>

                  <textarea
                    className="compose-title"
                    placeholder="Tiêu đề"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />

                  {/* 🔥 WRAPPER MỚI */}
                  <div className="compose-content-wrapper">
                    {/* HIGHLIGHT LAYER */}

                    {/* TEXTAREA */}
                    <textarea
                      className="compose-content"
                      placeholder="Bạn đang nghĩ gì?"
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                    />

                    {/* DROPDOWN */}
                  </div>

                  {/* ATTACHMENT FILE */}
                  <div className="attachmentSection">
                    <label className="attachBtn">
                      📎 Đính kèm tệp
                      <input
                        type="file"
                        multiple
                        onChange={handleAttachmentUpload}
                      />
                    </label>

                    {attachments.length > 0 && (
                      <div className="attachmentList">
                        {attachments.map((file, idx) => (
                          <div key={idx} className="attachmentItem">
                            <span className="fileName">📄 {file.name}</span>

                            <button
                              className="removeAttachment"
                              onClick={() => removeAttachment(idx)}
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="visibilitySelector" ref={menuRef}>
                    <span
                      className="dots"
                      onClick={() => setMenuOpen((prev) => !prev)}
                    >
                      {visibilityIcon[visibility]}
                      {visibilityText[visibility]} <KeyboardArrowDownIcon />
                    </span>
                    {menuOpen && (
                      <div className="visibilityMenu">
                        <div
                          className={`visibilityItem ${
                            visibility === "public" ? "active" : ""
                          }`}
                          onClick={() => setVisibility("public")}
                        >
                          <PublicIcon />
                          Công khai
                        </div>
                        <div
                          className={`visibilityItem ${
                            visibility === "follow" ? "active" : ""
                          }`}
                          onClick={() => setVisibility("follow")}
                        >
                          <BookmarkIcon />
                          Người theo dõi
                        </div>
                        <div
                          className={`visibilityItem ${
                            visibility === "private" ? "active" : ""
                          }`}
                          onClick={() => setVisibility("private")}
                        >
                          <SecurityIcon />
                          Chỉ mình tôi
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="selectDepartment">
                    <DepartmentMultiSelect
                      selectedDepartments={selectedDepartments}
                      setSelectedDepartments={setSelectedDepartments}
                    />
                    {/* <p>Đã chọn: {selectedDepartments.join(", ") || "Chưa chọn"}</p> */}
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CreatePost;
