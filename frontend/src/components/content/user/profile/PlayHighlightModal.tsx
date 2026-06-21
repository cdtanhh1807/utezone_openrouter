import React, { useState, useEffect, useRef } from "react";
import { StoryHighlightService } from "../../../../services/StoryHighlightService";
import { ToastService } from "../../../../services/ToastService";
import CloseIcon from "@mui/icons-material/Close";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditIcon from "@mui/icons-material/Edit";
import EditHighlightModal from "./EditHighlightModal";
import { format } from "date-fns";

interface PlayHighlightModalProps {
  isOpen: boolean;
  onClose: () => void;
  highlight: any; // populated highlight object
  isOwnProfile: boolean;
  onUpdated: () => void;
}

const PlayHighlightModal: React.FC<PlayHighlightModalProps> = ({
  isOpen,
  onClose,
  highlight,
  isOwnProfile,
  onUpdated,
}) => {
  const stories = highlight.stories || [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isEditOpen, setIsEditOpen] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const currentStory = stories[currentIndex];
  const totalStories = stories.length;

  // Xử lý chuyển tiếp tự động hoặc hết thời gian (5 giây cho ảnh)
  useEffect(() => {
    // Không chạy thời gian nếu đang mở modal chỉnh sửa
    if (isEditOpen || !currentStory) {
      setProgress(0);
      videoRef.current?.pause();
      audioRef.current?.pause();
      return;
    }

    setProgress(0);
    let animationFrameId: number;
    const startTime = Date.now();
    const duration = 5000; // 5s cho ảnh

    const update = () => {
      if (currentStory.mediaType === "video") {
        const vid = videoRef.current;
        if (vid) {
          if (vid.duration) {
            const start = currentStory.videoTrim?.startAt || 0;
            const storyDuration = currentStory.videoTrim?.duration || vid.duration || 5;
            const current = vid.currentTime - start;
            const percentage = Math.min((current / storyDuration) * 100, 100);
            setProgress(percentage);
            if (percentage >= 100) {
              handleNext();
              return;
            }
          }
        }
      } else {
        const elapsed = Date.now() - startTime;
        const percentage = Math.min((elapsed / duration) * 100, 100);
        setProgress(percentage);
        if (percentage >= 100) {
          handleNext();
          return;
        }
      }
      animationFrameId = requestAnimationFrame(update);
    };

    if (currentStory.mediaType === "video") {
      const vid = videoRef.current;
      if (vid) {
        vid.src = currentStory.mediaUrls?.[0] || "";
        vid.currentTime = currentStory.videoTrim?.startAt || 0;
        vid.play().catch(() => {});
      }
    }

    animationFrameId = requestAnimationFrame(update);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [currentIndex, currentStory, isEditOpen]);

  // Xử lý phát nhạc nền của story nếu có
  useEffect(() => {
    if (isEditOpen) return;

    const aud = audioRef.current;
    if (!aud) return;
    aud.pause();
    
    if (currentStory && currentStory.music && currentStory.music.url) {
      aud.src = currentStory.music.url;
      aud.currentTime = currentStory.music.startAt || 0;
      aud.play().catch(() => {});
      
      if (currentStory.music.duration) {
        const checkEnd = () => {
          const start = currentStory.music.startAt || 0;
          const end = start + currentStory.music.duration;
          if (aud.currentTime >= end) {
            aud.currentTime = start; // Loop
            aud.play();
          }
        };
        aud.ontimeupdate = checkEnd;
      }
    }
    return () => {
      aud.pause();
      aud.ontimeupdate = null;
    };
  }, [currentIndex, currentStory, isEditOpen]);

  const handleNext = () => {
    if (currentIndex < totalStories - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      onClose(); // Hết danh sách tin nổi bật
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };



  if (!isOpen || totalStories === 0) return null;

  return (
    <div className="highlight-play-overlay">
      <audio ref={audioRef} />

      {/* Close button */}
      <button className="play-close-btn" onClick={onClose}>
        <CloseIcon sx={{ fontSize: 30, color: "#fff" }} />
      </button>

      <div className="highlight-play-container">
        {/* Progress indicators */}
        <div className="highlight-progress-bar-row">
          {stories.map((_, index) => {
            let width = "0%";
            if (index < currentIndex) width = "100%";
            if (index === currentIndex) width = `${progress}%`;
            return (
              <div key={index} className="progress-bar-track">
                <div className="progress-bar-fill" style={{ width }} />
              </div>
            );
          })}
        </div>

        {/* User / Highlight Header info */}
        <div className="highlight-play-header">
          <div className="highlight-play-user-info">
            <span className="play-highlight-title">{highlight.title}</span>
            <span className="play-story-date">
              {format(new Date(currentStory.createdAt), "dd/MM/yyyy")}
            </span>
          </div>

          {/* Action button (Edit only) */}
          {isOwnProfile && (
            <div style={{ display: "flex", gap: "8px" }}>
              <button 
                className="play-edit-btn" 
                onClick={() => setIsEditOpen(true)} 
                title="Chỉnh sửa chủ đề"
              >
                <EditIcon sx={{ color: "#fff", fontSize: 20 }} />
              </button>
            </div>
          )}
        </div>

        {/* Media content */}
        <div className="highlight-media-area">
          {currentStory.mediaType === "video" ? (
            <video ref={videoRef} className="highlight-full-media" autoPlay playsInline />
          ) : (
            <img src={currentStory.mediaUrls?.[0]} alt="" className="highlight-full-media" />
          )}

          {/* Text layers overlay */}
          {currentStory.textLayers && currentStory.textLayers.map((layer: any, idx: number) => (
            <div
              key={layer.id || idx}
              style={{
                position: "absolute",
                left: `${layer.x * 100}%`,
                top: `${layer.y * 100}%`,
                color: layer.color || "#ffffff",
                fontSize: layer.fontSize ? `${layer.fontSize}px` : "16px",
                transform: `translate(-50%, -50%) scale(${layer.scale || 1}) rotate(${layer.rotate || 0}deg)`,
                fontFamily: layer.font || "Arial",
                textAlign: layer.align || "center",
                backgroundColor: layer.background || "transparent",
                padding: layer.background ? "4px 8px" : "0",
                borderRadius: "4px",
                pointerEvents: "none",
                zIndex: 10,
              }}
            >
              {layer.text}
            </div>
          ))}
        </div>

        {/* Navigation arrows */}
        <button className="nav-arrow-btn prev-arrow" onClick={handlePrev} disabled={currentIndex === 0}>
          <ChevronLeftIcon sx={{ fontSize: 40 }} />
        </button>
        <button className="nav-arrow-btn next-arrow" onClick={handleNext}>
          <ChevronRightIcon sx={{ fontSize: 40 }} />
        </button>
      </div>

      {/* Modal chỉnh sửa */}
      {isEditOpen && (
        <EditHighlightModal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          highlight={highlight}
          onUpdated={onUpdated}
          onDeleted={onClose}
        />
      )}
    </div>
  );
};

export default PlayHighlightModal;
