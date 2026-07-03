import LeftSide from "./components/content/user/home/leftSide";
import { Outlet } from "react-router-dom";
import './UserLayout.css';
import HeaderSide from "./components/content/user/home/headerSide";
import { AuthProvider } from "./components/content/user/chat/AuthContext";

const UserLayout = () => {
  return (
    <AuthProvider>
      <div className="main-layout">
        <div className="main-header">
          <HeaderSide/>
        </div>
        <div className="main-body">
          <div className="main-left-side">
            <LeftSide />
          </div>
          <div className="main-right-side">
            <Outlet />
          </div>
        </div>
      </div>
    </AuthProvider>
  );
};

export default UserLayout;
