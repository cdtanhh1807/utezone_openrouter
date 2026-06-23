import { Link, useLocation, useNavigate, Navigate } from "react-router-dom";
import { useState, type FormEvent, type ChangeEvent, useEffect } from "react";
import { AxiosError } from "axios";
import axiosInstance from "../../../../utils/AxiosInstance";
import { isTokenExpired } from '../../../../utils/Auth';
import logo from "../../../../assets/logo.png";
import './OtpForgotPassword.css';

const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;

function validatePassword(password: string): string | null {
    if (!passwordRegex.test(password)) {
        return "Mật khẩu phải >= 8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt.";
    }
    return null;
}

function OtpForgotPassword() {
    const location = useLocation();
    const navigate = useNavigate();
    const email = (location.state as { email: string })?.email;
    const [otp, setOtp] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        document.body.classList.add("login-page");
        return () => {
            document.body.classList.remove("login-page");
        };
    }, []);

    const token = localStorage.getItem('token');
    if (token && !isTokenExpired(token)) {
        return <Navigate to="/" replace />;
    }

    const handleChangePassword = (e: ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        if (name === "password") setPassword(value);
        if (name === "confirmPassword") setConfirmPassword(value);
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        if (password !== confirmPassword) {
            setError("Mật khẩu và xác nhận mật khẩu không khớp");
            setIsLoading(false);
            return;
        }

        const passwordErr = validatePassword(password);
        if (passwordErr) {
            setError(passwordErr);
            setIsLoading(false);
            return;
        }

        try {
            await axiosInstance.post("/account/change-password/", {
                email,
                otp,
                new_password: password
            });
            navigate("/login");
        } catch (err) {
            const error = err as AxiosError<{ message: string }>;
            setError(error.response?.data?.message || "OTP không đúng hoặc đã hết hạn.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-logo">
                    <img src={logo} alt="Logo" className="logo-img" />
                </div>

                <div className="slogan" style={{ fontSize: '22px', marginBottom: '10px' }}>
                    <span className="slogan-blue">Xác minh OTP</span>
                </div>
                <p style={{ textAlign: 'center', color: '#555', marginBottom: '20px', fontSize: '14px' }}>
                    Chúng tôi đã gửi mã OTP tới email: <b>{email}</b>
                </p>

                <form onSubmit={handleSubmit}>
                    <input
                        type="text"
                        placeholder="Nhập OTP"
                        value={otp}
                        onChange={e => setOtp(e.target.value)}
                        required
                    />
                    <input
                        type="password"
                        name="password"
                        placeholder="Mật khẩu mới"
                        value={password}
                        onChange={handleChangePassword}
                        required
                    />
                    <input
                        type="password"
                        name="confirmPassword"
                        placeholder="Xác nhận mật khẩu mới"
                        value={confirmPassword}
                        onChange={handleChangePassword}
                        required
                    />
                    <button type="submit" disabled={isLoading} className="signin-btn">
                        {isLoading ? "Đang xác minh..." : "Đổi mật khẩu"}
                    </button>
                    {error && <div className="error-message">{error}</div>}
                </form>

                <div className="create-account" style={{ marginTop: '10px' }}>
                    <Link to="/login">Quay lại đăng nhập</Link>
                </div>

                <div className="terms">
                    Copyright © 2026 utezone.site | Powered by utezone.site
                </div>
            </div>
        </div>
    );
}

export default OtpForgotPassword;