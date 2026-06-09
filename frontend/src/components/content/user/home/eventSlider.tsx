import { useEffect, useState } from "react";
import "./eventSlider.css";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { catalogService } from "../../../../services/CatalogService";
import { postAPI } from "../../../../services/PostService";
import AccountService from "../../../../services/AccountService";

import type { Catalog } from "../../../../types/Catalog";
import type { Post } from "../../../../types/Post";


interface CatalogView extends Catalog {
  title: string;
  content: string;
  image: string;
  pageName: string;
  avatar: string;
  end_at: string;
  post_id: string;
}

interface PostCatalogProps {
  onOpenPostDetail: (post: Post) => void;
}

export default function PostCatalog({
  onOpenPostDetail,
}: PostCatalogProps) {
  const [current, setCurrent] = useState(0);

  const [events, setEvents] = useState<CatalogView[]>([]);

  const [loading, setLoading] = useState(true);

  // ================= FETCH CATALOG =================
  useEffect(() => {
    const fetchCatalog = async () => {
      try {
        const res = await catalogService.getPostCatalog();

        const catalogs: Catalog[] =
          res?.post_catalog_list || [];

        const mappedData = await Promise.all(
          catalogs.map(async (catalog) => {
            try {
              // ===== GET POST =====
              const postRes =
                await postAPI.getById(
                  catalog.post_id
                );

              const post = postRes?.post;

              // ===== GET PAGE INFO =====
              const pageInfo =
                await AccountService.get_account_info(
                  post?.createdBy
                );

              return {
                ...catalog,

                post_id: catalog.post_id,

                title:
                  catalog.name ||
                  "Không có tiêu đề",

                content:
                  post?.ai_summary ||
                  post?.content ||
                  "Không có nội dung",

                image:
                  post?.thumbnails_url?.[0] ||
                  "https://images.unsplash.com/photo-1522202176988-66273c2fd55f",

                pageName:
                  pageInfo?.fullName ||
                  "UTEZone",

                avatar:
                  pageInfo?.avatar ||
                  "https://i.pravatar.cc/150?img=12",
              };
            } catch (err) {
              console.error(
                "Failed to fetch post:",
                catalog.post_id
              );

              return {
                ...catalog,

                post_id: catalog.post_id,

                title:
                  "Không thể tải bài viết",

                content: "",

                image:
                  "https://images.unsplash.com/photo-1522202176988-66273c2fd55f",

                pageName: "UTEZone",

                avatar:
                  "https://i.pravatar.cc/150?img=12",
              };
            }
          })
        );

        setEvents(mappedData);
      } catch (error) {
        console.error(
          "Failed to fetch catalog:",
          error
        );
      } finally {
        setLoading(false);
      }
    };

    fetchCatalog();
  }, []);

  // ================= AUTO SLIDE =================
  useEffect(() => {
    if (events.length === 0) return;

    const interval = setInterval(() => {
      setCurrent(
        (prev) => (prev + 1) % events.length
      );
    }, 5000);

    return () => clearInterval(interval);
  }, [events]);

  // ================= NEXT =================
  const nextSlide = () => {
    setCurrent(
      (prev) => (prev + 1) % events.length
    );
  };

  // ================= PREV =================
  const prevSlide = () => {
    setCurrent(
      (prev) =>
        (prev - 1 + events.length) %
        events.length
    );
  };

  // ================= LOADING =================
  if (loading) {
    return <div>Loading catalog...</div>;
  }

  // ================= EMPTY =================
  if (events.length === 0) {
    return <div>No catalog found</div>;
  }

  const event = events[current];

  return (
    <div
      className="event-slider"
      onClick={async () => {
        try {
          const res =
            await postAPI.getById(
              event.post_id
            );

          const fullPost =
            res.post || res;

          onOpenPostDetail(fullPost);
        } catch (err) {
          console.error(
            "Không lấy được post detail",
            err
          );
        }
      }}
    >
      {/* IMAGE */}
      <img
        src={event.image}
        alt={event.title}
        className="event-image"
      />

      {/* OVERLAY */}
      <div className="event-overlay">
        {/* TOP */}
        <div className="event-top">
          <div className="event-page">
            <img
              src={event.avatar}
              alt=""
              className="event-avatar"
            />

            <span className="event-page-name">
              {event.pageName}
            </span>
          </div>

          <p className="event-time">
            ⏰ Kết thúc:{" "}
            {new Date(
              event.end_at
            ).toLocaleString("vi-VN", {
              dateStyle: "short",
              timeStyle: "short",
            })}
          </p>
        </div>

        {/* CONTENT */}
        <div className="event-content">
          <h2 className="event-title">
            {event.title}
          </h2>
        </div>

        {/* LEFT BUTTON */}
        <button
          className="slide-btn left"
          onClick={(e) => {
            e.stopPropagation();
            prevSlide();
          }}
        >
          <ChevronLeft
            size={16}
            strokeWidth={3}
          />
        </button>

        {/* RIGHT BUTTON */}
        <button
          className="slide-btn right"
          onClick={(e) => {
            e.stopPropagation();
            nextSlide();
          }}
        >
          <ChevronRight
            size={16}
            strokeWidth={3}
          />
        </button>

        {/* DOTS */}
        <div className="event-dots">
          {events.map((_, index) => (
            <span
              key={index}
              className={`dot ${
                index === current
                  ? "active"
                  : ""
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}