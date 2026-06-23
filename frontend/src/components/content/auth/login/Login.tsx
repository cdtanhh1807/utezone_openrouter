import { useState, type ChangeEvent, type FormEvent } from "react";
import axiosInstance from "../../../../utils/AxiosInstance";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLoginBtn } from "../google/GoogleLoginBtn";
import logo from "../../../../assets/logo.png";
import { jwtDecode } from "jwt-decode";
import { ToastService } from "../../../../services/ToastService";
import AccountService from "../../../../services/AccountService";

import { useEffect } from "react";

import "./Login.css";

type LoginForm = {
  username: string;
  password: string;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
};

function Login() {
  const [formData, setFormData] = useState<LoginForm>({
    username: "",
    password: "",
  });

  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const navigate = useNavigate();

  const params = new URLSearchParams(window.location.search);
  const redirectUrl = params.get("redirect");

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    const payload = new URLSearchParams();
    payload.append("username", formData.username);
    payload.append("password", formData.password);

    try {
      const response = await axiosInstance.post<LoginResponse>(
        "/account/login",
        payload,
        {
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        }
      );

      const token = response.data.access_token;

      interface JwtPayload {
        sub: string;
        role: string;
        per: string;
        exp: number;
      }

      const decoded = jwtDecode<JwtPayload>(token);
      console.log("decoded login:", decoded);

      if (decoded.per === "000") {
        ToastService.error("Tài khoản của bạn đã bị khóa");
        return;
      }

      if (redirectUrl) {
        const separator = redirectUrl.includes("?") ? "&" : "?";
        window.location.href = `${redirectUrl}${separator}token=${token}`;
        return;
      }

      localStorage.setItem("token", token);

      if (decoded.role === "Administrator") {
        navigate("/admin");
        return;
      }

      let accountData;
      try {
        accountData = await AccountService.get_account_info(decoded.sub);
      } catch {
        navigate("/complete-profile");
        return;
      }

      if (!accountData.fullName?.trim()) {
        localStorage.setItem("account", JSON.stringify(accountData));
        navigate("/complete-profile");
        return;
      }

      navigate("/home");
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError("Sai tên đăng nhập hoặc mật khẩu");
      } else {
        setError("Không thể kết nối đến server");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Thêm class vào body khi mount component
    document.body.classList.add("login-page");
    return () => {
      // Xóa class khi unmount
      document.body.classList.remove("login-page");
    };
  }, []);

  return (
    <div className="login-container">
      <div className="login-card">
        {/* Logo */}
        <div className="login-logo">
          <img src={logo} alt="Logo" className="logo-img" />
        </div>

        {/* Slogan - gộp một dòng */}
        <div className="slogan">
          <span className="slogan-blue">Diễn đàn sinh viên</span>
          <span className="slogan-text"> Trường Đại học Công nghệ Kỹ thuật TP. HCM</span>
        </div>

        {/* Divider "Đăng nhập vào UTEZone" */}
        <div className="divider">Đăng nhập vào UTEZone</div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            name="username"
            placeholder="Email"
            value={formData.username}
            onChange={handleChange}
            required
          />

          <div className="password-wrapper">
            <input
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder="Mật khẩu"
              value={formData.password}
              onChange={handleChange}
              required
            />
            <span
              className="toggle-password"
              onClick={() => setShowPassword(!showPassword)}
            >
            </span>
          </div>

          <div className="options">
            <Link to="/forgot-password" className="forgot">
              Quên mật khẩu ?
            </Link>
          </div>

          <button type="submit" disabled={isLoading} className="signin-btn">
            {isLoading ? "Đang đăng nhập..." : "Đăng nhập"}
          </button>

          {error && <div className="error-message">{error}</div>}
        </form>

        <div className="create-account">
          <Link to="/signup">Tạo tài khoản mới</Link>
        </div>

        {/* Social divider with "Hoặc tiếp tục với" */}
        <div className="social-divider">
          <span>Hoặc</span>
        </div>

        <div className="social-login">
          <GoogleLoginBtn />
        </div>

        <div className="terms">
          Copyright © 2026 utezone.site | Powered by utezone.site
        </div>
      </div>
    </div>
  );
}

export default Login;