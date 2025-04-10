import React, { useState, useEffect, useCallback, createContext } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import axios from "axios";
import jwt_decode from "jwt-decode";
import io from "socket.io-client";
import Login from "./Login";
import AdminDashboard from "./AdminDashboard";
import UserDashboard from "./UserDashboard";

const API_BASE_URL = "http://192.168.213.152:5000/api";
const SOCKET_URL = "http://192.168.213.152:5000"; // WebSocket server URL

// Create Cart Context
export const CartContext = createContext();

const App = () => {
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cartItems, setCartItems] = useState([]);
  const [error, setError] = useState(null); // Error state for displaying messages
  const navigate = useNavigate();

  // Initialize WebSocket
  const socket = io(SOCKET_URL, {
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    transports: ["websocket"], // Force WebSocket transport
  });

  // Logout Function
  const logoutUser = useCallback(() => {
    console.warn("Logging out user...");
    localStorage.removeItem("access_token");
    setRole(null);
    setCartItems([]); // Clear cart on logout
    navigate("/login");
    setTimeout(() => window.location.reload(), 100);
  }, [navigate]);

  // Centralized Token Validation
  const validateToken = useCallback(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      console.warn("No token found in localStorage.");
      return null;
    }

    try {
      const decoded = jwt_decode(token);
      console.log("Decoded token:", decoded);
      if (!decoded.exp || Date.now() >= decoded.exp * 1000) {
        console.error("Token expired. Expiry:", new Date(decoded.exp * 1000));
        logoutUser(); // Automatically log out if token is expired
        return null;
      }
      return { token, role: decoded.role };
    } catch (error) {
      console.error("Invalid token format or decoding error:", error.message);
      return null;
    }
  }, [logoutUser]);

  // Check Token on Mount
  useEffect(() => {
    const auth = validateToken();
    setRole(auth ? auth.role : null);
    setLoading(false);
  }, [validateToken]);

  // Fetch Protected Data with Query Parameter Support
  const fetchProtectedData = useCallback(
    async (endpoint, method = "get", data = null, params = {}) => {
      const auth = validateToken();
      if (!auth) {
        console.warn("No valid token. Redirecting to login.");
        logoutUser();
        return null;
      }

      const config = {
        headers: {
          Authorization: `Bearer ${auth.token}`,
          "Content-Type": "application/json",
        },
        withCredentials: true,
        params,
      };

      // Ensure data is JSON stringified for POST/PATCH to force Content-Type
      if (method.toLowerCase() !== "get" && data) {
        config.data = JSON.parse(JSON.stringify(data)); // Deep clone to ensure clean object
      }

      console.log(`Fetching ${endpoint} with method: ${method}, token:`, auth.token, "config:", config);

      try {
        const response = await axios({
          method: method.toLowerCase(),
          url: `${API_BASE_URL}/${endpoint}`,
          ...config,
        });
        console.log(`Data from ${endpoint}:`, response.data);
        return response.data;
      } catch (error) {
        const errorDetails = {
          status: error.response?.status,
          message: error.response?.data?.error || error.message,
          endpoint,
          requestConfig: config,
        };
        console.error(`Error fetching ${endpoint}:`, errorDetails);
        if (error.response?.status === 401) {
          console.warn("Unauthorized. Logging out due to 401 response.");
          logoutUser();
        } else if (error.response?.status === 415) {
          console.warn("Unsupported Media Type. Expected 'application/json'. Config:", config);
        } else if (error.response?.status === 422) {
          console.warn("Unprocessable Entity. Check request parameters:", params, data);
        } else if (error.response?.status === 500) {
          console.error("Server error (500) occurred:", error.response?.data);
        }
        throw error;
      }
    },
    [validateToken, logoutUser]
  );

  // Fetch Cart Items
  const fetchCartItems = useCallback(async () => {
    try {
      const data = await fetchProtectedData("cart", "get");
      console.log("Fetched cart items:", data);
      setCartItems(data.cart || []);
    } catch (error) {
      console.error("Error fetching cart items:", error);
      setError("Failed to load cart items. Please try again.");
    }
  }, [fetchProtectedData]);

  // Add Item to Cart
  const addToCart = async (serviceId) => {
    try {
      await fetchProtectedData("cart", "post", { service_id: serviceId, quantity: 1 });
      await fetchCartItems(); // Refresh cart items after adding
    } catch (error) {
      console.error("Error adding item to cart:", error);
      setError("Failed to add item to cart. Please try again.");
    }
  };

  // Remove Item from Cart
  const removeCartItem = async (cartItemId) => {
    try {
      await fetchProtectedData(`cart/${cartItemId}`, "delete");
      await fetchCartItems(); // Refresh cart items after removal
    } catch (error) {
      console.error("Error removing item from cart:", error);
      setError("Failed to remove item from cart. Please try again.");
    }
  };

  // Place an Order
  const placeOrder = async () => {
    try {
      await fetchProtectedData("orders", "post", { cart_items: cartItems });
      setCartItems([]); // Clear cart after placing order
    } catch (error) {
      console.error("Error placing order:", error);
      setError("Failed to place order. Please try again.");
    }
  };

  // Fetch Cart Items on Mount
  useEffect(() => {
    if (role === "user") {
      fetchCartItems();
    }
  }, [role, fetchCartItems]);

  // Listen for Real-Time Cart Updates
  useEffect(() => {
    socket.on("cart_updated", (updatedCart) => {
      console.log("Cart updated via WebSocket:", updatedCart);
      setCartItems((prevCartItems) => {
        if (JSON.stringify(prevCartItems) !== JSON.stringify(updatedCart.cart)) {
          return updatedCart.cart || [];
        }
        return prevCartItems;
      });
    });

    socket.on("connect_error", (error) => {
      console.error("WebSocket connection error:", error);
      setTimeout(() => socket.connect(), 5000); // Reconnect after 5 seconds
    });

    return () => {
      socket.disconnect();
    };
  }, [socket]);

  // Debugging: Log cartItems whenever it changes
  useEffect(() => {
    console.log("Cart Items Updated:", cartItems);
  }, [cartItems]);

  if (loading) {
    return <div style={styles.loading}>Loading...</div>;
  }

  return (
    <CartContext.Provider value={{ cartItems, addToCart, removeCartItem, placeOrder }}>
      <div style={styles.container}>
        {role && (
          <button onClick={logoutUser} style={styles.logoutButton}>
            Logout
          </button>
        )}

        {/* Display error messages */}
        {error && <div style={styles.error}>{error}</div>}

        <Routes>
          <Route path="/login" element={<Login setRole={setRole} />} />
          <Route
            path="/admin-dashboard"
            element={
              role === "admin" ? (
                <AdminDashboard fetchProtectedData={fetchProtectedData} logoutUser={logoutUser} />
              ) : (
                <Navigate to="/login" />
              )
            }
          />
          <Route
            path="/user-dashboard"
            element={
              role === "user" ? (
                <UserDashboard fetchProtectedData={fetchProtectedData} logoutUser={logoutUser} />
              ) : (
                <Navigate to="/login" />
              )
            }
          />
          <Route
            path="*"
            element={<Navigate to={role ? (role === "admin" ? "/admin-dashboard" : "/user-dashboard") : "/login"} />}
          />
        </Routes>
      </div>
    </CartContext.Provider>
  );
};

// Styling with Mobile Optimization
const styles = {
  container: {
    padding: "20px",
    minHeight: "100vh",
    position: "relative",
    backgroundColor: "#f0f2f5",
  },
  loading: {
    fontSize: "20px",
    fontWeight: "bold",
    color: "#555",
    textAlign: "center",
    marginTop: "50px",
  },
  logoutButton: {
    position: "fixed",
    top: "10px",
    right: "10px",
    padding: "10px 15px",
    backgroundColor: "#FF3B3B",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "16px",
    zIndex: 1000,
  },
  error: {
    position: "fixed",
    top: "50px",
    right: "10px",
    padding: "10px 15px",
    backgroundColor: "#FF3B3B",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    fontSize: "14px",
    zIndex: 1000,
  },
};

export default App;