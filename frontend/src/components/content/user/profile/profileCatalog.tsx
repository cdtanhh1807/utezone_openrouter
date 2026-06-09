// ProfileCatalog.tsx

import { useEffect, useState } from "react";
import "./profileCatalog.css";

import { catalogService } from "../../../../services/CatalogService";
import { postAPI } from "../../../../services/PostService";

import type { Catalog } from "../../../../types/Catalog";

// ADD IMPORT
import { MoreHorizontal, Pencil } from "lucide-react";

import { useRef } from "react";

import CreatePostCatalogModal from "../create/createPostCatalog";
import PostDetail from "../post/postDetail";

interface CatalogView extends Catalog {
  title: string;
  image: string;
  content: string;
}

function ProfileCatalog() {
  const [catalogs, setCatalogs] = useState<CatalogView[]>([]);

  const [loading, setLoading] = useState(true);
  // ADD STATE

  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const [selectedCatalogPostId, setSelectedCatalogPostId] = useState("");

  const [openUpdateModal, setOpenUpdateModal] = useState(false);

  const [activePost, setActivePost] = useState<any>(null);
  const [isPostDetailOpen, setIsPostDetailOpen] = useState(false);

  // ADD FUNCTION

  const handleOpenUpdate = (postId: string) => {
    setSelectedCatalogPostId(postId);

    setOpenUpdateModal(true);

    setOpenMenuId(null);
  };

  const handleOpenPost = async (postId: string) => {
    try {
      const res = await postAPI.getById(postId);
      const post = res.post || res;

      setActivePost(post);
      setIsPostDetailOpen(true);
    } catch (err) {
      console.error("Lỗi mở bài viết", err);
    }
  };
  const openOriginalPost = async (originalPostId: string) => {
    try {
      const res = await postAPI.getById(originalPostId);
      const originalPost = res.post || res;

      setIsPostDetailOpen(false);
      requestAnimationFrame(() => {
        setActivePost(originalPost);
        setIsPostDetailOpen(true);
      });
    } catch (err) {
      console.error("Không lấy được bài viết gốc", err);
    }
  };
  const refreshPost = async (postId: string) => {
    const updated = await postAPI.getById(postId);
    const updatedPost = updated.post || updated;
    setActivePost(updatedPost);
  };

  useEffect(() => {
    fetchMyCatalog();
  }, []);

  const fetchMyCatalog = async () => {
    try {
      const res = await catalogService.getMyPostCatalog();

      const catalogList = res?.post_catalog_list || [];

      const mappedData = await Promise.all(
        catalogList.map(async (item: Catalog) => {
          try {
            const postRes = await postAPI.getById(item.post_id);

            const post = postRes?.post;

            return {
              ...item,
              title: post?.title || "Không có tiêu đề",

              content: post?.ai_summary || post?.content || "",

              image: post?.thumbnails_url?.[0] || "",
            };
          } catch (error) {
            console.error(error);

            return {
              ...item,
              title: "Không thể tải bài viết",
              content: "",
              image: "",
            };
          }
        }),
      );

      setCatalogs(mappedData);
    } catch (error) {
      console.error("Failed to fetch catalogs", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="catalog-loading">Đang tải sự kiện...</div>;
  }

  return (
    <div className="profile-catalog-container">
      <div className="catalog-header">
        <h2>Sự kiện của bạn</h2>

        <p>Quản lý tất cả sự kiện đã ghim</p>
      </div>

      {catalogs.length === 0 ? (
        <div className="catalog-empty">Chưa có sự kiện nào</div>
      ) : (
        <div className="catalog-grid">
          {catalogs.map((item) => (
            <div
              className="catalog-card"
              key={item._id}
              onClick={() => handleOpenPost(item.post_id)}
            >
              {/* TOP ACTION */}
              <div className="catalog-action">
                <button
                  className="catalog-action-btn"
                  onClick={() => {
                    setOpenMenuId(
                      openMenuId === item._id ? null : item._id || null,
                    );
                  }}
                >
                  <p className="catalog-action-text">...</p>
                </button>

                {openMenuId === item._id && (
                  <div className="catalog-dropdown">
                    <div
                      className="catalog-dropdown-item"
                      onClick={() => handleOpenUpdate(item.post_id)}
                    >
                      <Pencil size={15} />
                      Chỉnh sửa
                    </div>
                  </div>
                )}
              </div>
              {/* IMAGE */}
              <div className="catalog-image-wrapper">
                <img
                  src={item.image}
                  alt={item.title}
                  className="catalog-image"
                />

                <div className="catalog-badge">📌 Sự kiện nổi bật</div>
              </div>

              {/* CONTENT */}
              <div className="catalog-card-content">
                <h3>{item.name}</h3>

                <p className="catalog-post-title">{item.title}</p>

                <p className="catalog-desc">{item.content}</p>

                {/* <div className="catalog-date">
                  <span>
                    Bắt đầu:
                  </span>

                  {new Date(
                    item.begin_at
                  ).toLocaleString()}
                </div> */}

                <div className="catalog-date">
                  <span>Kết thúc:</span>

                  {new Date(item.end_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <CreatePostCatalogModal
        open={openUpdateModal}
        onClose={() => setOpenUpdateModal(false)}
        postId={selectedCatalogPostId}
        isCreateCatalog={true}
        onSuccess={() => {
          fetchMyCatalog();
        }}
      />
      {isPostDetailOpen && activePost && (
        <PostDetail
          activePost={activePost}
          onClose={() => setIsPostDetailOpen(false)}
          onCommentAdded={refreshPost}
          onOpenOriginalPost={openOriginalPost}
        />
      )}
    </div>
  );
}

export default ProfileCatalog;
