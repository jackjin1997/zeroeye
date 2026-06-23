package orderbook

import (
	"testing"

	"github.com/shopspring/decimal"
	"github.com/tent-of-trials/market/types"
)

// TestCancelBidRemovesBidLevelAndOrder verifies cancellation clears depth and the order index.
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

// TestCancelBidPreservesOtherPriceLevels verifies cancellation removes only the matching level.
func TestCancelBidPreservesOtherPriceLevels(t *testing.T) {
	book := newTestOrderBook()
	orders := []*types.Order{
		newTestOrder("bid-100", types.Buy, "100.00", "1.00"),
		newTestOrder("bid-99", types.Buy, "99.00", "2.00"),
		newTestOrder("bid-98", types.Buy, "98.00", "3.00"),
	}

	for _, order := range orders {
		if _, err := book.AddOrder(order); err != nil {
			t.Fatalf("AddOrder(%s) error = %v", order.ID, err)
		}
	}

	if err := book.CancelOrder("bid-99"); err != nil {
		t.Fatalf("CancelOrder() error = %v", err)
	}

	bids := book.GetSnapshot().Bids
	if got := len(bids); got != 2 {
		t.Fatalf("bid depth after cancel = %d, want 2", got)
	}
	if !bids[0].Price.Equal(decimal.RequireFromString("100.00")) {
		t.Fatalf("best bid after cancel = %s, want 100.00", bids[0].Price)
	}
	if !bids[1].Price.Equal(decimal.RequireFromString("98.00")) {
		t.Fatalf("second bid after cancel = %s, want 98.00", bids[1].Price)
	}
	if _, exists := book.orders["bid-99"]; exists {
		t.Fatal("cancelled middle bid still exists in order index")
	}
}

// TestCancelOneBidAtSharedPriceKeepsRemainingDepth verifies one same-price order remains visible.
func TestCancelOneBidAtSharedPriceKeepsRemainingDepth(t *testing.T) {
	book := newTestOrderBook()
	first := newTestOrder("bid-first", types.Buy, "100.00", "2.00")
	second := newTestOrder("bid-second", types.Buy, "100.00", "3.00")

	for _, order := range []*types.Order{first, second} {
		if _, err := book.AddOrder(order); err != nil {
			t.Fatalf("AddOrder(%s) error = %v", order.ID, err)
		}
	}

	if err := book.CancelOrder(first.ID); err != nil {
		t.Fatalf("CancelOrder() error = %v", err)
	}

	bids := book.GetSnapshot().Bids
	if got := len(bids); got != 1 {
		t.Fatalf("bid depth after one same-price cancel = %d, want 1", got)
	}
	if !bids[0].Price.Equal(decimal.RequireFromString("100.00")) {
		t.Fatalf("remaining bid price = %s, want 100.00", bids[0].Price)
	}
	if !bids[0].Quantity.Equal(decimal.RequireFromString("3.00")) {
		t.Fatalf("remaining bid quantity = %s, want 3.00", bids[0].Quantity)
	}
	if bids[0].Count != 1 {
		t.Fatalf("remaining bid count = %d, want 1", bids[0].Count)
	}
	if _, exists := book.orders[first.ID]; exists {
		t.Fatal("cancelled same-price bid still exists in order index")
	}
	if _, exists := book.orders[second.ID]; !exists {
		t.Fatal("remaining same-price bid was removed from order index")
	}
}

// TestCancelAskRemovesAskLevel verifies ask cancellation clears the matching depth level.
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

// TestCancelUnknownOrderReturnsErrOrderNotFound verifies unknown IDs return the documented error.
func TestCancelUnknownOrderReturnsErrOrderNotFound(t *testing.T) {
	book := newTestOrderBook()

	if err := book.CancelOrder("missing-order"); err != ErrOrderNotFound {
		t.Fatalf("CancelOrder() error = %v, want %v", err, ErrOrderNotFound)
	}
}

// TestClosedBookRejectsAddAndCancel verifies closed books reject both supported mutations.
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

// TestSnapshotReturnsCopiesOfBidAndAskLevels verifies callers cannot mutate internal depth.
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

// newTestOrderBook returns a consistently configured order book for focused tests.
func newTestOrderBook() *OrderBook {
	return NewOrderBook("BTC-USD", Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 2,
	})
}

// newTestOrder returns a limit order with matching total and remaining quantities.
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
