import React, { useState, useEffect, useCallback } from "react";
import io from "socket.io-client";

const SOCKET_URL = "http://192.168.213.152:5000"; // WebSocket server URL
const socket = io(SOCKET_URL, {
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
});

const serviceCategories = ["all", "cleaning", "food", "groceries", "fruits", "gardening"];

const UserDashboard = ({ fetchProtectedData, logoutUser }) => {
  const [services, setServices] = useState([]);
  const [orders, setOrders] = useState([]);
  const [cartItems, setCartItems] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [servicesPage, setServicesPage] = useState(1);
  const [ordersPage, setOrdersPage] = useState(1);
  const [servicesTotalPages, setServicesTotalPages] = useState(1);
  const [ordersTotalPages, setOrdersTotalPages] = useState(1);
  const [loading, setLoading] = useState({ services: false, orders: false, cart: false });
  const [error, setError] = useState(null);

  // Payment Form State
  const [paymentDetails, setPaymentDetails] = useState({ phone: "", amount: "" });

  // Track Order State
  const [trackedOrder, setTrackedOrder] = useState(null);
  const [orderIdToTrack, setOrderIdToTrack] = useState("");

  // Fetch Services by Category with Pagination
  const fetchServicesByCategory = useCallback(async (page = 1) => {
    setLoading((prev) => ({ ...prev, services: true }));
    setError(null);

    try {
      if (selectedCategory === "all") {
        const categoryPromises = serviceCategories
          .filter((cat) => cat !== "all")
          .map((cat) =>
            fetchProtectedData(`services/${cat}`, "get", null, { page, per_page: 5 })
          );
        const responses = await Promise.all(categoryPromises);
        const allServices = responses.flatMap((res) => res.services || []);
        setServices(allServices);
        setServicesTotalPages(1); // Adjust based on your pagination logic
      } else {
        const data = await fetchProtectedData(`services/${selectedCategory}`, "get", null, {
          page,
          per_page: 5,
        });
        setServices(data.services || []);
        setServicesTotalPages(data.pages || 1);
      }
      setServicesPage(page);
    } catch (error) {
      console.error(`Error fetching services for ${selectedCategory}:`, error);
      setError(error.response?.data?.error || "Failed to load services.");
    } finally {
      setLoading((prev) => ({ ...prev, services: false }));
    }
  }, [selectedCategory, fetchProtectedData]);

  // Fetch User Orders with Pagination
  const fetchOrders = useCallback(
    async (page = 1) => {
      setLoading((prev) => ({ ...prev, orders: true }));
      setError(null);

      try {
        const data = await fetchProtectedData("orders/my", "get", null, { page, per_page: 5 });
        setOrders(data.orders || []);
        setOrdersTotalPages(data.pages || 1);
        setOrdersPage(page);
      } catch (error) {
        console.error("Error fetching orders:", error);
        setError(error.response?.data?.error || "Failed to load orders.");
        if (error.response?.status === 401) {
          logoutUser();
        }
      } finally {
        setLoading((prev) => ({ ...prev, orders: false }));
      }
    },
    [fetchProtectedData, logoutUser]
  );

  // Fetch Cart Items
  const fetchCartItems = useCallback(async () => {
    setLoading((prev) => ({ ...prev, cart: true }));
    setError(null);

    try {
      const data = await fetchProtectedData("cart", "get");
      console.log("Fetched cart items:", data); // Debugging: Log the response
      setCartItems(data.cart || []); // Ensure the correct response structure is used
    } catch (error) {
      console.error("Error fetching cart items:", error);
      setError(error.response?.data?.error || "Failed to load cart items.");
      if (error.response?.status === 401) {
        logoutUser();
      }
    } finally {
      setLoading((prev) => ({ ...prev, cart: false }));
    }
  }, [fetchProtectedData, logoutUser]);

  // Add Item to Cart
  const addToCart = async (serviceId) => {
    setError(null);
    try {
      const response = await fetchProtectedData("cart", "post", { service_id: serviceId, quantity: 1 });
      console.log("Item added to cart:", response); // Debugging: Log the response
      fetchCartItems(); // Refresh cart items after adding
    } catch (error) {
      console.error("Error adding item to cart:", error);
      setError(error.response?.data?.error || "Failed to add item to cart.");
    }
  };

  // Remove Item from Cart
  const removeCartItem = async (cartItemId) => {
    setError(null);
    try {
      await fetchProtectedData(`cart/${cartItemId}`, "delete");
      fetchCartItems(); // Refresh cart items after removal
    } catch (error) {
      console.error("Error removing item from cart:", error);
      setError(error.response?.data?.error || "Failed to remove item from cart.");
    }
  };

  // Place an Order
  const placeOrder = async () => {
    setError(null);
    try {
      const response = await fetchProtectedData("orders", "post", { cart_items: cartItems });
      console.log("Order placed successfully:", response);
      setCartItems([]); // Clear cart after placing order
      fetchOrders(ordersPage); // Refresh orders
    } catch (error) {
      console.error("Error placing order:", error);
      setError(error.response?.data?.error || "Failed to place order.");
    }
  };

  // Track an Order
  const trackOrder = async () => {
    setError(null);
    try {
      const data = await fetchProtectedData(`orders/${orderIdToTrack}`, "get");
      setTrackedOrder(data.order);
    } catch (error) {
      console.error("Error fetching order:", error);
      setError("Failed to fetch order details.");
    }
  };

  // Initiate Payment
  const initiatePayment = async () => {
    setError(null);
    try {
      const response = await fetchProtectedData("mpesa/payment", "post", {
        phone_number: paymentDetails.phone,
        amount: paymentDetails.amount,
      });
      console.log("Payment initiated:", response);
      setError(null);
    } catch (error) {
      console.error("Error initiating payment:", error);
      setError("Failed to initiate payment.");
    }
  };

  // Fetch Data on Component Load or Category/Page Change
  useEffect(() => {
    fetchServicesByCategory(servicesPage);
    fetchOrders(ordersPage);
    fetchCartItems();
  }, [fetchServicesByCategory, fetchOrders, fetchCartItems, servicesPage, ordersPage]);

  // Listen for Real-Time Updates
  useEffect(() => {
    socket.on("order_updated", (updatedOrder) => {
      setOrders((prevOrders) =>
        prevOrders.map((order) =>
          order.order_id === updatedOrder.order_id ? updatedOrder : order
        )
      );
    });

    socket.on("cart_updated", (updatedCart) => {
      console.log("Cart updated via WebSocket:", updatedCart); // Debugging: Log the WebSocket event
      setCartItems(updatedCart.cart || []); // Ensure the correct response structure is used
    });

    socket.on("connect_error", (error) => {
      console.error("WebSocket connection error:", error);
      setTimeout(() => socket.connect(), 5000); // Reconnect after 5 seconds
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // Debugging: Log cartItems whenever it changes
  useEffect(() => {
    console.log("Cart Items Updated:", cartItems);
  }, [cartItems]);

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>User Dashboard</h1>

      {(loading.services || loading.orders || loading.cart) && <p style={styles.loading}>Loading...</p>}
      {error && <p style={styles.error}>{error}</p>}

      {/* Category Selection */}
      <div style={styles.filterContainer}>
        <label style={styles.label}>Filter by Category:</label>
        <select
          value={selectedCategory}
          onChange={(e) => {
            setSelectedCategory(e.target.value);
            setServicesPage(1);
          }}
          style={styles.select}
        >
          {serviceCategories.map((category) => (
            <option key={category} value={category}>
              {category.charAt(0).toUpperCase() + category.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Services Section */}
      <h2 style={styles.subHeader}>Available Services ({selectedCategory})</h2>
      {services.length > 0 ? (
        <>
          <ul style={styles.list}>
            {services.map((service) => (
              <li key={service.id} style={styles.listItem}>
                <div style={styles.serviceDetails}>
                  <strong>{service.name}</strong> - {service.price.toLocaleString()} {service.currency || "KES"}
                </div>
                <button
                  onClick={() => addToCart(service.id)}
                  style={{ ...styles.orderButton, ...(loading.cart ? styles.disabledButton : {}) }}
                  disabled={loading.cart}
                >
                  Add to Cart
                </button>
              </li>
            ))}
          </ul>
          {selectedCategory !== "all" && (
            <div style={styles.pagination}>
              <button
                onClick={() => setServicesPage((prev) => Math.max(prev - 1, 1))}
                disabled={servicesPage === 1 || loading.services}
                style={{
                  ...styles.pageButton,
                  ...(servicesPage === 1 || loading.services ? styles.disabledButton : {}),
                }}
              >
                Previous
              </button>
              <span style={styles.pageInfo}>
                Page {servicesPage} of {servicesTotalPages}
              </span>
              <button
                onClick={() => setServicesPage((prev) => Math.min(prev + 1, servicesTotalPages))}
                disabled={servicesPage === servicesTotalPages || loading.services}
                style={{
                  ...styles.pageButton,
                  ...(servicesPage === servicesTotalPages || loading.services ? styles.disabledButton : {}),
                }}
              >
                Next
              </button>
            </div>
          )}
        </>
      ) : (
        <p>No services available.</p>
      )}

      {/* Cart Section */}
      <h2 style={styles.subHeader}>Your Cart</h2>
      {cartItems.length > 0 ? (
        <>
          <ul style={styles.list}>
            {cartItems.map((item) => (
              <li key={item.id} style={styles.listItem}>
                <div style={styles.serviceDetails}>
                  <strong>{item.service_name || "Unknown Service"}</strong> -{" "}
                  {item.price ? item.price.toLocaleString() : "N/A"} {item.currency || "KES"} <br />
                  <strong>Quantity:</strong> {item.quantity || 1} <br />
                  <strong>Total Price:</strong> {(item.price * item.quantity).toLocaleString()} {item.currency || "KES"}
                </div>
                <button
                  onClick={() => removeCartItem(item.id)}
                  style={{ ...styles.removeButton, ...(loading.cart ? styles.disabledButton : {}) }}
                  disabled={loading.cart}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={placeOrder}
            style={{ ...styles.orderButton, ...(loading.orders ? styles.disabledButton : {}) }}
            disabled={loading.orders}
          >
            Place Order
          </button>
        </>
      ) : (
        <p>Your cart is empty.</p>
      )}

      {/* Orders Section */}
      <h2 style={styles.subHeader}>Your Orders</h2>
      {orders.length > 0 ? (
        <>
          <ul style={styles.list}>
            {orders.map((order) => (
              <li key={order.order_id} style={styles.listItem}>
                <strong>Order ID:</strong> {order.order_id} <br />
                <strong>Service:</strong> {order.service_name || "Unknown"} <br />
                <strong>Quantity:</strong> {order.quantity} <br />
                <strong>Total Price:</strong> {order.total_price.toLocaleString()} {order.currency || "KES"} <br />
                <strong>Status:</strong> {order.status} <br />
                <strong>Created At:</strong> {new Date(order.created_at).toLocaleString()}
              </li>
            ))}
          </ul>
          <div style={styles.pagination}>
            <button
              onClick={() => setOrdersPage((prev) => Math.max(prev - 1, 1))}
              disabled={ordersPage === 1 || loading.orders}
              style={{
                ...styles.pageButton,
                ...(ordersPage === 1 || loading.orders ? styles.disabledButton : {}),
              }}
            >
              Previous
            </button>
            <span style={styles.pageInfo}>
              Page {ordersPage} of {ordersTotalPages}
            </span>
            <button
              onClick={() => setOrdersPage((prev) => Math.min(prev + 1, ordersTotalPages))}
              disabled={ordersPage === ordersTotalPages || loading.orders}
              style={{
                ...styles.pageButton,
                ...(ordersPage === ordersTotalPages || loading.orders ? styles.disabledButton : {}),
              }}
            >
              Next
            </button>
          </div>
        </>
      ) : (
        <p>No orders found.</p>
      )}

      {/* Track Order Section */}
      <h2 style={styles.subHeader}>Track Your Order</h2>
      <div style={styles.trackOrderContainer}>
        <input
          type="text"
          placeholder="Enter Order ID"
          value={orderIdToTrack}
          onChange={(e) => setOrderIdToTrack(e.target.value)}
          style={styles.input}
        />
        <button onClick={trackOrder} style={styles.trackButton}>
          Track Order
        </button>
      </div>
      {trackedOrder && (
        <div style={styles.trackedOrderDetails}>
          <h3>Order Details</h3>
          <p><strong>Order ID:</strong> {trackedOrder.order_id}</p>
          <p><strong>Status:</strong> {trackedOrder.status}</p>
          <p><strong>Created At:</strong> {new Date(trackedOrder.created_at).toLocaleString()}</p>
        </div>
      )}

      {/* Payment Form Section */}
      <h2 style={styles.subHeader}>Make Payment</h2>
      <div style={styles.paymentForm}>
        <input
          type="text"
          placeholder="Phone Number"
          value={paymentDetails.phone}
          onChange={(e) => setPaymentDetails({ ...paymentDetails, phone: e.target.value })}
          style={styles.input}
        />
        <input
          type="number"
          placeholder="Amount"
          value={paymentDetails.amount}
          onChange={(e) => setPaymentDetails({ ...paymentDetails, amount: e.target.value })}
          style={styles.input}
        />
        <button onClick={initiatePayment} style={styles.payButton}>
          Pay Now
        </button>
      </div>
    </div>
  );
};

// Styles
const styles = {
  container: {
    padding: "20px",
    maxWidth: "90%",
    margin: "0 auto",
    backgroundColor: "#f8f9fa",
    borderRadius: "10px",
    boxShadow: "0px 0px 10px rgba(0, 0, 0, 0.1)",
    fontFamily: "Arial, sans-serif",
    minHeight: "100vh",
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
  filterContainer: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "20px",
    flexWrap: "wrap",
  },
  label: {
    fontSize: "16px",
    fontWeight: "bold",
  },
  select: {
    padding: "8px",
    fontSize: "16px",
    borderRadius: "5px",
    border: "1px solid #ccc",
    minWidth: "150px",
  },
  list: {
    listStyleType: "none",
    padding: 0,
  },
  listItem: {
    padding: "15px",
    backgroundColor: "#fff",
    borderRadius: "5px",
    marginBottom: "10px",
    boxShadow: "0px 2px 5px rgba(0, 0, 0, 0.1)",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
  },
  serviceDetails: {
    flex: "1 1 60%",
    minWidth: "200px",
  },
  orderButton: {
    padding: "8px 15px",
    backgroundColor: "#28A745",
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
    opacity: "0.6",
    cursor: "not-allowed",
  },
  pageInfo: {
    fontSize: "14px",
  },
  trackOrderContainer: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
  },
  input: {
    padding: "8px",
    fontSize: "14px",
    borderRadius: "5px",
    border: "1px solid #ccc",
    flex: 1,
  },
  trackButton: {
    padding: "8px 15px",
    backgroundColor: "#007BFF",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "14px",
  },
  trackedOrderDetails: {
    padding: "15px",
    backgroundColor: "#fff",
    borderRadius: "5px",
    marginBottom: "20px",
    boxShadow: "0px 2px 5px rgba(0, 0, 0, 0.1)",
  },
  paymentForm: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
  },
  payButton: {
    padding: "8px 15px",
    backgroundColor: "#28A745",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "14px",
  },
};

export default UserDashboard;