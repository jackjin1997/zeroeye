package orderbook

import (
	"testing"

	"github.com/shopspring/decimal"
	"github.com/tent-of-trials/market/types"
)

func TestCancelBidRemovesBidLevelAndOrder(t *testing.T) {
	book := newTestOrderBook()
	order := newTestOrder("bid-1", types.Buy, "100.00", "2.50")

	if _, err := book.AddOrder(order); err != nil {
		t.Fatalf("AddOrder() error = %v", err)
	}
	if got := len(book.GetSnapshot().Bids); got != 1 {
		t.Fatalf("bid depth before cancel = %d, want 1", got)
	}

	if err := book.CancelOrder(order.ID); err != nil {
		t.Fatalf("CancelOrder() error = %v", err)
	}

	snapshot := book.GetSnapshot()
	if got := len(snapshot.Bids); got != 0 {
		t.Fatalf("bid depth after cancel = %d, want 0", got)
	}
	if _, exists := book.orders[order.ID]; exists {
		t.Fatalf("cancelled bid %q still exists in order index", order.ID)
	}
	if order.Status != types.Cancelled {
		t.Fatalf("order status = %v, want Cancelled", order.Status)
	}
}

func TestCancelAskRemovesAskLevel(t *testing.T) {
	book := newTestOrderBook()
	order := newTestOrder("ask-1", types.Sell, "101.00", "1.25")

	if _, err := book.AddOrder(order); err != nil {
		t.Fatalf("AddOrder() error = %v", err)
	}
	if got := len(book.GetSnapshot().Asks); got != 1 {
		t.Fatalf("ask depth before cancel = %d, want 1", got)
	}

	if err := book.CancelOrder(order.ID); err != nil {
		t.Fatalf("CancelOrder() error = %v", err)
	}

	if got := len(book.GetSnapshot().Asks); got != 0 {
		t.Fatalf("ask depth after cancel = %d, want 0", got)
	}
}

func TestCancelUnknownOrderReturnsErrOrderNotFound(t *testing.T) {
	book := newTestOrderBook()

	if err := book.CancelOrder("missing-order"); err != ErrOrderNotFound {
		t.Fatalf("CancelOrder() error = %v, want %v", err, ErrOrderNotFound)
	}
}

func TestClosedBookRejectsAddAndCancel(t *testing.T) {
	book := newTestOrderBook()
	book.Close()

	if _, err := book.AddOrder(newTestOrder("bid-1", types.Buy, "100.00", "1.00")); err != ErrBookClosed {
		t.Fatalf("AddOrder() error = %v, want %v", err, ErrBookClosed)
	}
	if err := book.CancelOrder("bid-1"); err != ErrBookClosed {
		t.Fatalf("CancelOrder() error = %v, want %v", err, ErrBookClosed)
	}
}

func TestSnapshotReturnsCopiesOfBidAndAskLevels(t *testing.T) {
	book := newTestOrderBook()
	bid := newTestOrder("bid-1", types.Buy, "100.00", "2.00")
	ask := newTestOrder("ask-1", types.Sell, "101.00", "3.00")

	if _, err := book.AddOrder(bid); err != nil {
		t.Fatalf("AddOrder(bid) error = %v", err)
	}
	if _, err := book.AddOrder(ask); err != nil {
		t.Fatalf("AddOrder(ask) error = %v", err)
	}

	snapshot := book.GetSnapshot()
	snapshot.Bids[0].Price = decimal.NewFromInt(1)
	snapshot.Bids[0].Quantity = decimal.NewFromInt(1)
	snapshot.Asks[0].Price = decimal.NewFromInt(999)
	snapshot.Asks[0].Quantity = decimal.NewFromInt(999)

	fresh := book.GetSnapshot()
	if !fresh.Bids[0].Price.Equal(decimal.RequireFromString("100.00")) {
		t.Fatalf("fresh bid price = %s, want original 100.00", fresh.Bids[0].Price)
	}
	if !fresh.Bids[0].Quantity.Equal(decimal.RequireFromString("2.00")) {
		t.Fatalf("fresh bid quantity = %s, want original 2.00", fresh.Bids[0].Quantity)
	}
	if !fresh.Asks[0].Price.Equal(decimal.RequireFromString("101.00")) {
		t.Fatalf("fresh ask price = %s, want original 101.00", fresh.Asks[0].Price)
	}
	if !fresh.Asks[0].Quantity.Equal(decimal.RequireFromString("3.00")) {
		t.Fatalf("fresh ask quantity = %s, want original 3.00", fresh.Asks[0].Quantity)
	}
}

func newTestOrderBook() *OrderBook {
	return NewOrderBook("BTC-USD", Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 2,
	})
}

func newTestOrder(id string, side types.OrderSide, price, quantity string) *types.Order {
	qty := decimal.RequireFromString(quantity)
	return &types.Order{
		ID:           id,
		Symbol:       "BTC-USD",
		Side:         side,
		Type:         types.Limit,
		Price:        decimal.RequireFromString(price),
		Quantity:     qty,
		RemainingQty: qty,
	}
}
