import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import SummaryBox from "../summary/summaryPost";
import { useAIStore } from "../stores/aiStore";
import PostDetail from "../post/postDetail";
import { postAPI } from "../../../../services/PostService";
import type { Post } from "../../../../types/Post";

const AISummaryPortal = () => {
  const {
    summary,
    postId,
    showSummary,
    closeSummary,
  } = useAIStore();

  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  useEffect(() => {
    if (!showSummary) {
      // Reset state khi summary tắt để tránh lỗi lưu trữ trạng thái hiển thị postDetail
      setIsDetailOpen(false);
      setSelectedPost(null);
      return;
    }

    let isActive = false;
    // Trì hoãn kích hoạt để tránh sự kiện click mở ban đầu kích hoạt đóng ngay lập tức
    const timeout = setTimeout(() => {
      isActive = true;
    }, 50);

    const handleClickOutside = (event: MouseEvent) => {
      if (!isActive) return;
      if (isDetailOpen) return; // Không đóng summaryBox nếu đang mở postDetail modal

      const summaryBox = document.querySelector(".summary-box");
      if (summaryBox && !summaryBox.contains(event.target as Node)) {
        closeSummary();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      clearTimeout(timeout);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showSummary, closeSummary, isDetailOpen]);

  if (!showSummary) return null;

  const handleViewDetail = async () => {
    if (!postId) return;
    try {
      const res = await postAPI.getById(postId);
      setSelectedPost(res.post);
      setIsDetailOpen(true);
    } catch (err) {
      console.error("Failed to load post detail:", err);
    }
  };

  return createPortal(
    <>
      <div
        style={{
          position: "fixed",
          top: "200px",
          left: "350px",
          zIndex: 900, // Nhỏ hơn z-index của postDetail modal (1000)
        }}
      >
        <SummaryBox
          summary={summary}
          postId={postId}
          onClose={closeSummary}
          onViewDetail={handleViewDetail}
        />
      </div>

      {isDetailOpen && selectedPost && (
        <PostDetail
          activePost={selectedPost}
          onClose={() => setIsDetailOpen(false)}
          onCommentAdded={() => {}}
          onOpenOriginalPost={() => {}}
          onPostDeleted={() => setIsDetailOpen(false)}
          onActivePostUpdate={(updatedPost: Post) => {
            setSelectedPost(updatedPost);
          }}
        />
      )}
    </>,
    document.body,
  );
};

export default AISummaryPortal;