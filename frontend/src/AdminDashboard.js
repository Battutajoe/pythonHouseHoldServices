import React, { useState, useEffect, useCallback } from "react";
import io from "socket.io-client";

const SOCKET_URL = "http://192.168.213.152:5000"; // WebSocket server URL
const socket = io(SOCKET_URL, {
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
});

const AdminDashboard = ({ fetchProtectedData, logoutUser }) => {
  const [orders, setOrders] = useState([]);
  const [cartItems, setCartItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Fetch Orders with Pagination
  const fetchOrders = useCallback(
    async (page = 1) => {
      setLoading(true);
      setError(null);

      try {
        const data = await fetchProtectedData("orders", "get", null, { page, per_page: 5 });
        if (!data || !data.orders) {
          throw new Error("Invalid response structure");
        }
        setOrders(data.orders);
        setTotalPages(data.pages || 1);
        setCurrentPage(page);
      } catch (error) {
        console.error("Error fetching orders:", error);
        setError(error.response?.data?.error || "Failed to fetch orders.");
        if (error.response?.status === 401) {
          logoutUser();
        }
      } finally {
        setLoading(false);
      }
    },
    [fetchProtectedData, logoutUser]
  );

  // Fetch Cart Items
  const fetchCartItems = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchProtectedData("cart", "get");
      if (!data || !data.cart) {
        throw new Error("Invalid response structure");
      }
      setCartItems(data.cart);
    } catch (error) {
      console.error("Error fetching cart items:", error);
      setError(error.response?.data?.error || "Failed to fetch cart items.");
      if (error.response?.status === 401) {
        logoutUser();
      }
    } finally {
      setLoading(false);
    }
  }, [fetchProtectedData, logoutUser]);

  // Remove Item from Cart
  const removeCartItem = async (cartItemId) => {
    setError(null);
    try {
      await fetchProtectedData(`cart/${cartItemId}`, "delete");
      fetchCartItems(); // Refresh cart items
    } catch (error) {
      console.error("Error removing item from cart:", error);
      setError(error.response?.data?.error || "Failed to remove item from cart.");
      if (error.response?.status === 401) {
        logoutUser();
      }
    }
  };

  // Update Order Status
  const updateOrderStatus = async (orderId, newStatus) => {
    setError(null);
    try {
      const data = await fetchProtectedData(`orders/${orderId}`, "patch", { status: newStatus });
      if (!data || !data.order) {
        throw new Error("Invalid response structure");
      }
      setOrders((prevOrders) =>
        prevOrders.map((order) =>
          order.order_id === orderId ? { ...order, status: newStatus } : order
        )
      );
    } catch (error) {
      console.error("Error updating order status:", error);
      setError(error.response?.data?.error || "Failed to update order status.");
      if (error.response?.status === 401) {
        logoutUser();
      }
    }
  };

  // Confirm Order
  const confirmOrder = async (orderId) => {
    setError(null);
    try {
      const data = await fetchProtectedData(`orders/${orderId}/confirm`, "patch");
      if (!data || !data.order) {
        throw new Error("Invalid response structure");
      }
      setOrders((prevOrders) =>
        prevOrders.map((order) =>
          order.order_id === orderId ? { ...order, is_confirmed: true } : order
        )
      );
    } catch (error) {
      console.error("Error confirming order:", error);
      setError(error.response?.data?.error || "Failed to confirm order.");
      if (error.response?.status === 401) {
        logoutUser();
      }
    }
  };

  // Process Payment
  const processPayment = async (orderId) => {
    setError(null);
    try {
      const data = await fetchProtectedData(`orders/${orderId}/process-payment`, "patch");
      if (!data || !data.order) {
        throw new Error("Invalid response structure");
      }
      setOrders((prevOrders) =>
        prevOrders.map((order) =>
          order.order_id === orderId ? { ...order, is_paid: true } : order
        )
      );
    } catch (error) {
      console.error("Error processing payment:", error);
      setError(error.response?.data?.error || "Failed to process payment.");
      if (error.response?.status === 401) {
        logoutUser();
      }
    }
  };

  // Pagination Controls
  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages && !loading) {
      fetchOrders(newPage);
    }
  };

  // Listen for Real-Time Updates
  useEffect(() => {
    fetchOrders(currentPage);
    fetchCartItems();

    socket.on("order_updated", (updatedOrder) => {
      setOrders((prevOrders) =>
        prevOrders.map((order) =>
          order.order_id === updatedOrder.order_id ? updatedOrder : order
        )
      );
    });

    socket.on("cart_updated", (updatedCart) => {
      console.log("Cart updated via WebSocket:", updatedCart); // Debugging: Log the WebSocket event
      setCartItems(updatedCart.cart || []); // Ensure the correct response structure
    });

    socket.on("connect_error", (error) => {
      console.error("WebSocket connection error:", error);
      setTimeout(() => socket.connect(), 5000); // Reconnect after 5 seconds
    });

    return () => {
      socket.disconnect();
    };
  }, [fetchOrders, fetchCartItems, currentPage]);

  // Debugging: Log cartItems whenever it changes
  useEffect(() => {
    console.log("Cart Items Updated:", cartItems);
  }, [cartItems]);

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>Admin Dashboard</h1>

      {loading && <p style={styles.loading}>Loading...</p>}
      {error && <p style={styles.error}>{error}</p>}

      {/* Cart Section */}
      <h2 style={styles.subHeader}>Cart</h2>
      {cartItems.length === 0 ? (
        <p>No items in the cart.</p>
      ) : (
        <ul style={styles.cartList}>
          {cartItems.map((item) => (
            <li key={item.id} style={styles.cartItem}>
              <div style={styles.cartDetails}>
                <strong>Service:</strong> {item.service_name || "Unknown Service"} <br />
                <strong>Quantity:</strong> {item.quantity} <br />
                <strong>Price:</strong> {item.price.toLocaleString()} {item.currency || "KES"} <br />
                <strong>Total:</strong> {(item.price * item.quantity).toLocaleString()} {item.currency || "KES"} <br />
              </div>
              <button
                onClick={() => removeCartItem(item.id)}
                style={styles.removeButton}
                disabled={loading}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Orders Section */}
      <h2 style={styles.subHeader}>Orders</h2>
      {orders.length === 0 ? (
        <p>No orders available.</p>
      ) : (
        <>
          <ul style={styles.orderList}>
            {orders.map((order) => (
              <li key={order.order_id} style={styles.orderItem}>
                <div style={styles.orderDetails}>
                  <strong>Order ID:</strong> {order.order_id} <br />
                  <strong>User:</strong> {order.username || "Unknown User"} <br />
                  <strong>Service:</strong> {order.service_name || "Unknown Service"} <br />
                  <strong>Total:</strong> {order.total_price.toLocaleString()} {order.currency || "KES"} <br />
                  <strong>Status:</strong> {order.status} <br />
                  <strong>Confirmed:</strong> {order.is_confirmed ? "Yes" : "No"} <br />
                  <strong>Paid:</strong> {order.is_paid ? "Yes" : "No"} <br />
                  <strong>Created:</strong> {new Date(order.created_at).toLocaleString()} <br />
                </div>
                <div style={styles.actions}>
                  <select
                    value={order.status}
                    onChange={(e) => updateOrderStatus(order.order_id, e.target.value)}
                    style={styles.statusDropdown}
                    disabled={loading}
                  >
                    <option value="Pending">Pending</option>
                    <option value="Processing">Processing</option>
                    <option value="Completed">Completed</option>
                    <option value="Cancelled">Cancelled</option>
                  </select>
                  {!order.is_confirmed && (
                    <button
                      onClick={() => confirmOrder(order.order_id)}
                      style={{ ...styles.confirmButton, ...(loading ? styles.disabledButton : {}) }}
                      disabled={loading}
                    >
                      Confirm Order
                    </button>
                  )}
                  {!order.is_paid && (
                    <button
                      onClick={() => processPayment(order.order_id)}
                      style={{ ...styles.payButton, ...(loading ? styles.disabledButton : {}) }}
                      disabled={loading}
                    >
                      Process Payment
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>

          {/* Pagination Controls */}
          <div style={styles.pagination}>
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1 || loading}
              style={{
                ...styles.pageButton,
                ...(currentPage === 1 || loading ? styles.disabledButton : {}),
              }}
            >
              Previous
            </button>
            <span style={styles.pageInfo}>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages || loading}
              style={{
                ...styles.pageButton,
                ...(currentPage === totalPages || loading ? styles.disabledButton : {}),
              }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
};

// Styles with Mobile Optimization
const styles = {
  container: {
    padding: "20px",
    maxWidth: "90%",
    margin: "0 auto",
    backgroundColor: "#f8f9fa",
    borderRadius: "10px",
    boxShadow: "0px 0px 10px rgba(0, 0, 0, 0.1)",
    minHeight: "100vh",
    fontFamily: "Arial, sans-serif",
  },
  header: {
    fontSize: "clamp(1.5rem, 5vw, 2rem)",
    textAlign: "center",
    marginBottom: "20px",
  },
  subHeader: {
    fontSize: "clamp(1rem, 4vw, 1.5rem)",
    margin: "20px 0 10px",
  },
  error: {
    color: "red",
    fontWeight: "bold",
    textAlign: "center",
    margin: "10px 0",
  },
  loading: {
    textAlign: "center",
    color: "#555",
    margin: "10px 0",
  },
  cartList: {
    listStyleType: "none",
    padding: 0,
  },
  cartItem: {
    marginBottom: "15px",
    padding: "15px",
    border: "1px solid #ddd",
    borderRadius: "5px",
    backgroundColor: "#fff",
    boxShadow: "2px 2px 5px rgba(0,0,0,0.1)",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cartDetails: {
    flex: 1,
  },
  removeButton: {
    padding: "8px 15px",
    backgroundColor: "#FF3B3B",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "14px",
  },
  orderList: {
    listStyleType: "none",
    padding: 0,
  },
  orderItem: {
    marginBottom: "15px",
    padding: "15px",
    border: "1px solid #ddd",
    borderRadius: "5px",
    backgroundColor: "#fff",
    boxShadow: "2px 2px 5px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
  },
  orderDetails: {
    flex: "1 1 60%",
    minWidth: "200px",
  },
  actions: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  statusDropdown: {
    padding: "8px",
    borderRadius: "5px",
    border: "1px solid #ccc",
    fontSize: "14px",
    minWidth: "120px",
  },
  confirmButton: {
    padding: "8px 15px",
    backgroundColor: "#28A745",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "14px",
  },
  payButton: {
    padding: "8px 15px",
    backgroundColor: "#007BFF",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "14px",
  },
  pagination: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    gap: "15px",
    marginTop: "20px",
  },
  pageButton: {
    padding: "8px 15px",
    backgroundColor: "#007BFF",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "14px",
  },
  disabledButton: {
    opacity: 0.6,
    cursor: "not-allowed",
  },
  pageInfo: {
    fontSize: "14px",
  },
};

export default AdminDashboard;