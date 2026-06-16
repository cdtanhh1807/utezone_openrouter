import "./home.css";
import MiddleSide from "./middleSide";
import RightSide from "./rightSide";
import SearchSide from "../search/searchSide";
import { useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";

function Home() {
  const location = useLocation();
  const navigate = useNavigate();
  const isSearching = location.pathname === "/search";

  useEffect(() => {
  if (isSearching) {
    const container = document.querySelector(
      ".main-right-side"
    ) as HTMLElement | null;

    container?.scrollTo({
      top: 0,
      behavior: "auto",
    });
  }
}, [isSearching, location.search]);


  useEffect(() => {
    if (location.state?.fromLogin) {
      // 🧹 Xóa state để tránh loop
      navigate(location.pathname, { replace: true, state: {} });
      window.location.reload();
    }
  }, []);

  return (
    <div className="Home">
      <div className="middleSide">
        {isSearching ? <SearchSide /> : <MiddleSide />}
      </div>

      <div className="rightSide">
        <RightSide />
      </div>
    </div>
  );
}

export default Home;


// 16/6/2026
