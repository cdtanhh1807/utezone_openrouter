import React, { useEffect, useState, useRef } from "react";
import { StoryHighlightService } from "../../../../services/StoryHighlightService";
import FileService from "../../../../services/FileService";
import CloseIcon from "@mui/icons-material/Close";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { ToastService } from "../../../../services/ToastService";
import { format } from "date-fns";

interface CreateHighlightModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const CreateHighlightModal: React.FC<CreateHighlightModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const [title, setTitle] = useState("");
  const [coverUrl, setCoverUrl] = useState("");
  const [archiveStories, setArchiveStories] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadingCover, setUploadingCover] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const fetchArchive = async () => {
      try {
        const res = await StoryHighlightService.getArchive();
        if (res.success) {
          setArchiveStories(res.data || []);
        }
      } catch (err) {
        console.error("Error fetching story archive:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchArchive();
  }, []);

  const handleToggleSelect = (storyId: string) => {
    setSelectedIds((prev) =>
      prev.includes(storyId)
        ? prev.filter((id) => id !== storyId)
        : [...prev, storyId]
    );
  };

  const handleUploadCover = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingCover(true);
    try {
      const res = await FileService.uploadFromCrawl(file);
      if (res.url) {
        setCoverUrl(res.url);
        ToastService.success("Tải lên ảnh bìa thành công!");
      }
    } catch (err) {
      console.error("Upload cover error:", err);
      ToastService.error("Không thể tải lên ảnh đại diện");
    } finally {
      setUploadingCover(false);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) {
      ToastService.error("Vui lòng nhập tên chủ đề nổi bật");
      return;
    }
    if (selectedIds.length === 0) {
      ToastService.error("Vui lòng chọn ít nhất một tin");
      return;
    }

    try {
      // Nếu chưa chọn ảnh bìa, tự động lấy ảnh của story đầu tiên được chọn
      let finalCover = coverUrl;
      if (!finalCover) {
        const firstSelectedStory = archiveStories.find(
          (s) => s.id === selectedIds[0] || s._id === selectedIds[0]
        );
        finalCover = firstSelectedStory?.mediaUrls?.[0] || "";
      }

      const res = await StoryHighlightService.addHighlight({
        title: title.trim(),
        storyIds: selectedIds,
        coverUrl: finalCover,
      });
      if (res.success) {
        ToastService.success("Đã tạo tin nổi bật thành công!");
        onCreated();
        onClose();
      }
    } catch (err) {
      console.error("Error creating highlight:", err);
      ToastService.error("Có lỗi xảy ra khi lưu tin nổi bật");
    }
  };

  const getSelectedStories = () => {
    return archiveStories.filter((s) =>
      selectedIds.includes(s.id || s._id)
    );
  };

  const isVideoUrl = (url: string) => {
    if (!url) return false;
    const matchingStory = archiveStories.find((s) => s.mediaUrls?.[0] === url);
    if (matchingStory) {
      return matchingStory.mediaType === "video";
    }
    const videoExtensions = [".mp4", ".webm", ".ogg", ".mov", ".m4v"];
    return videoExtensions.some((ext) =>
      url.toLowerCase().endsWith(ext) || url.toLowerCase().includes(ext + "?")
    );
  };

  if (!isOpen) return null;

  return (
    <div className="highlight-modal-overlay">
      <div className="highlight-modal-box">
        {/* Header */}
        <div className="highlight-modal-header">
          <h2>Tạo tin nổi bật mới</h2>
          <button className="close-modal-btn" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        {/* Body */}
        <div className="highlight-modal-body">
          {/* Title Input */}
          <div className="highlight-input-group">
            <label htmlFor="hl-title">Tên chủ đề:</label>
            <input
              id="hl-title"
              type="text"
              placeholder="Ví dụ: Family, Friends..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={15}
            />
          </div>

          {/* Cover Photo Selection */}
          <div className="cover-selector-section">
            <label className="section-sublabel">Ảnh đại diện chủ đề:</label>
            <div className="cover-preview-row">
              <div className="current-cover-circle">
                {(() => {
                  const activeCoverUrl = coverUrl || getSelectedStories()[0]?.mediaUrls?.[0] || "";
                  if (!activeCoverUrl) {
                    return <div className="current-cover-blank" />;
                  }
                  return isVideoUrl(activeCoverUrl) ? (
                    <video
                      src={activeCoverUrl}
                      className="current-cover-img"
                      muted
                      playsInline
                    />
                  ) : (
                    <img
                      src={activeCoverUrl}
                      alt="Cover Preview"
                      className="current-cover-img"
                    />
                  );
                })()}
              </div>

              <div className="cover-upload-actions">
                <button
                  type="button"
                  className="btn-upload-cover"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingCover}
                >
                  <CloudUploadIcon />
                  <span>{uploadingCover ? "Đang tải lên..." : "Tải ảnh từ máy"}</span>
                </button>
                <input
                  type="file"
                  ref={fileInputRef}
                  style={{ display: "none" }}
                  accept="image/*"
                  onChange={handleUploadCover}
                />
              </div>
            </div>

            {/* Chọn từ các tin đã chọn */}
            {selectedIds.length > 0 && (
              <div className="quick-cover-select">
                <span className="quick-select-label">Hoặc chọn từ các tin đã tích:</span>
                <div className="quick-cover-thumbs">
                  {getSelectedStories().map((story) => {
                    const url = story.mediaUrls?.[0];
                    if (!url) return null;
                    const storyId = story.id || story._id;
                    const isActive = coverUrl === url || (!coverUrl && getSelectedStories()[0]?.mediaUrls?.[0] === url);
                    
                    return story.mediaType === "video" ? (
                      <video
                        key={storyId}
                        src={url}
                        className={`quick-thumb-option ${isActive ? "active" : ""}`}
                        onClick={() => setCoverUrl(url)}
                        muted
                        playsInline
                      />
                    ) : (
                      <img
                        key={storyId}
                        src={url}
                        alt=""
                        className={`quick-thumb-option ${isActive ? "active" : ""}`}
                        onClick={() => setCoverUrl(url)}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <label className="section-sublabel">Chọn tin từ kho lưu trữ của bạn:</label>
          
          {loading ? (
            <div className="archive-loading">Đang tải kho lưu trữ...</div>
          ) : archiveStories.length > 0 ? (
            <div className="archive-grid">
              {archiveStories.map((story) => {
                const storyId = story.id || story._id;
                const isSelected = selectedIds.includes(storyId);
                const mediaUrl = story.mediaUrls?.[0] || "/default-avatar.png";
                
                return (
                  <div
                    key={storyId}
                    className={`archive-grid-item ${isSelected ? "selected" : ""}`}
                    onClick={() => handleToggleSelect(storyId)}
                  >
                    {story.mediaType === "video" ? (
                      <video src={mediaUrl} className="archive-media-thumb" />
                    ) : (
                      <img src={mediaUrl} alt="" className="archive-media-thumb" />
                    )}
                    
                    {/* Tick indicator */}
                    {isSelected && (
                      <div className="select-tick">
                        <CheckCircleIcon sx={{ color: "#0866ff" }} />
                      </div>
                    )}
                    
                    {/* Creation Date Overlay */}
                    <div className="archive-date-overlay">
                      {format(new Date(story.createdAt), "dd/MM/yyyy")}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="archive-empty">Bạn chưa đăng story nào hoặc kho lưu trữ trống</div>
          )}
        </div>

        {/* Footer */}
        <div className="highlight-modal-footer">
          <button className="btn-cancel" onClick={onClose}>
            Hủy
          </button>
          <button className="btn-save" onClick={handleSave}>
            Lưu tin nổi bật
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreateHighlightModal;
