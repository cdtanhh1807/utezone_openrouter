import React from "react";
import "./middleSide.css";

import ListPost from "../profile/profilePost";
import StoryBlock from "../create/storyBlock";

import { useAIModerationStore } from "../stores/aiModerationStore";

const MiddleSide: React.FC = () => {
  const isModerating = useAIModerationStore((state) => state.isModerating);

  return (
    <div className="middleHomeSide">
      <div className="storyHome">
        <StoryBlock />
      </div>

      {isModerating && (
        <div className="aiModerationBanner">
          <div className="aiSpinner"></div>

          <div>
            <h4>AI đang kiểm duyệt bài viết</h4>

            <p>Nội dung đang được phân tích...</p>
          </div>
        </div>
      )}

      <div className="listPostHome">
        <ListPost />
      </div>
    </div>
  );
};

export default MiddleSide;
