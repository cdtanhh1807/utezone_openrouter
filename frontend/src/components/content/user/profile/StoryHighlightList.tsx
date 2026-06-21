import React, { useEffect, useState } from "react";
import { jwtDecode } from "jwt-decode";
import { StoryHighlightService } from "../../../../services/StoryHighlightService";
import CreateHighlightModal from "./CreateHighlightModal";
import PlayHighlightModal from "./PlayHighlightModal";
import "../home/middleSide.css"; // Nhập để dùng chung style StoryBlock
import "./StoryHighlight.css";

interface StoryHighlightListProps {
  email?: string; // Email của chủ sở hữu profile
  onLoadComplete?: (count: number) => void;
}

const StoryHighlightList: React.FC<StoryHighlightListProps> = ({ email, onLoadComplete }) => {
  const [highlights, setHighlights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [openCreate, setOpenCreate] = useState(false);
  const [openPlay, setOpenPlay] = useState(false);
  const [activeHighlight, setActiveHighlight] = useState<any | null>(null);

  // Giải mã token để xác định email người dùng đang đăng nhập
  const token = localStorage.getItem("token");
  let decodedEmail: string | null = null;
  if (token) {
    try {
      const decoded: any = jwtDecode(token);
      decodedEmail = decoded.sub;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }
  const targetEmail = email || decodedEmail;
  const isOwnProfile = targetEmail === decodedEmail;

  const fetchHighlights = async () => {
    if (!targetEmail) return;
    try {
      const res = await StoryHighlightService.getByUser(targetEmail);
      if (res.success) {
        const dataList = res.data || [];
        setHighlights(dataList);
        onLoadComplete?.(dataList.length);
      }
    } catch (err) {
      console.error("❌ Lỗi lấy danh sách tin nổi bật:", err);
      onLoadComplete?.(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHighlights();
  }, [targetEmail]);

  const handlePlayHighlight = (hl: any) => {
    if (hl.stories && hl.stories.length > 0) {
      setActiveHighlight(hl);
      setOpenPlay(true);
    }
  };

  const isVideoUrl = (url: string, stories: any[]) => {
    if (!url) return false;
    const matchingStory = stories?.find((s) => s.mediaUrls?.[0] === url);
    if (matchingStory) {
      return matchingStory.mediaType === "video";
    }
    const videoExtensions = [".mp4", ".webm", ".ogg", ".mov", ".m4v"];
    return videoExtensions.some((ext) =>
      url.toLowerCase().endsWith(ext) || url.toLowerCase().includes(ext + "?")
    );
  };

  const borderColors = ["#0866ff", "#45bd62", "#9360f7", "#f7b928", "#f35369"];

  return (
    <div className="storyBlock highlight-block" style={{ width: "100%", height: "100px" }}>
      {/* Nút thêm mới tin nổi bật (Chỉ hiển thị trên trang cá nhân của mình) */}
      {isOwnProfile && (
        <div className="storyPaticular" onClick={() => setOpenCreate(true)}>
          <div className="imageDIv-story addHighlightCircle">
            <span className="plusIcon-highlight">+</span>
          </div>
          <div className="profileName">Mới</div>
        </div>
      )}

      {/* Danh sách các chủ đề nổi bật */}
      {highlights.map((hl, idx) => {
        const cover = hl.coverUrl || hl.stories?.[0]?.mediaUrls?.[0] || "/default-avatar.png";
        const hlId = hl.id || hl._id;
        const isVideoCover = isVideoUrl(cover, hl.stories || []);
        const borderColor = borderColors[idx % borderColors.length];
        
        return (
          <div
            key={hlId}
            className="storyPaticular"
            onClick={() => handlePlayHighlight(hl)}
          >
            <div className="imageDIv-story" style={{ borderColor }}>
              {isVideoCover ? (
                <video src={cover} className="statusImg-story" muted playsInline />
              ) : (
                <img src={cover} alt={hl.title} className="statusImg-story" />
              )}
            </div>
            <div className="profileName" title={hl.title}>{hl.title}</div>
          </div>
        );
      })}

      {!loading && highlights.length === 0 && !isOwnProfile && (
        <span className="highlight-empty-text" style={{ fontSize: 13, color: "#8a8d91" }}>
          Không có tin nổi bật nào
        </span>
      )}

      {/* Modal tạo mới */}
      {openCreate && (
        <CreateHighlightModal
          isOpen={openCreate}
          onClose={() => setOpenCreate(false)}
          onCreated={fetchHighlights}
        />
      )}

      {/* Trình phát tin nổi bật */}
      {openPlay && activeHighlight && (
        <PlayHighlightModal
          isOpen={openPlay}
          onClose={() => {
            setOpenPlay(false);
            setActiveHighlight(null);
          }}
          highlight={activeHighlight}
          isOwnProfile={isOwnProfile}
          onUpdated={fetchHighlights}
        />
      )}
    </div>
  );
};

export default StoryHighlightList;
