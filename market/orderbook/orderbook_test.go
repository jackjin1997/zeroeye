package orderbook

import (
	"testing"

	"github.com/shopspring/decimal"
	"github.com/tent-of-trials/market/types"
)

func newTestBook() *OrderBook {
	return NewOrderBook("BTC-USD", Config{MaxDepth: 10})
}

func limitOrder(id string, side types.OrderSide, price string, qty string) *types.Order {
	return &types.Order{
		ID:           id,
		Side:         side,
		Price:        decimal.RequireFromString(price),
		RemainingQty: decimal.RequireFromString(qty),
	}
}

func TestCancelBidRemovesLevelAndOrder(t *testing.T) {
	ob := newTestBook()
	order := limitOrder("bid-1", types.Buy, "100", "1")
	if _, err := ob.AddOrder(order); err != nil {
		t.Fatalf("AddOrder: %v", err)
	}

	if err := ob.CancelOrder("bid-1"); err != nil {
		t.Fatalf("CancelOrder: %v", err)
	}
	if err := ob.CancelOrder("bid-1"); err != ErrOrderNotFound {
		t.Fatalf("expected ErrOrderNotFound after cancel, got %v", err)
	}
	if len(ob.GetBids()) != 0 {
		t.Fatalf("expected empty bids, got %d", len(ob.GetBids()))
	}
}

func TestCancelAskRemovesLevel(t *testing.T) {
	ob := newTestBook()
	order := limitOrder("ask-1", types.Sell, "101", "2")
	if _, err := ob.AddOrder(order); err != nil {
		t.Fatalf("AddOrder: %v", err)
	}

	if err := ob.CancelOrder("ask-1"); err != nil {
		t.Fatalf("CancelOrder: %v", err)
	}
	if len(ob.GetAsks()) != 0 {
		t.Fatalf("expected empty asks, got %d", len(ob.GetAsks()))
	}
}

func TestCancelUnknownOrderReturnsErrOrderNotFound(t *testing.T) {
	ob := newTestBook()
	if err := ob.CancelOrder("missing"); err != ErrOrderNotFound {
		t.Fatalf("expected ErrOrderNotFound, got %v", err)
	}
}

func TestClosedBookRejectsAddAndCancel(t *testing.T) {
	ob := newTestBook()
	ob.Close()

	if _, err := ob.AddOrder(limitOrder("", types.Buy, "100", "1")); err != ErrBookClosed {
		t.Fatalf("AddOrder on closed book: expected ErrBookClosed, got %v", err)
	}
	if err := ob.CancelOrder("any"); err != ErrBookClosed {
		t.Fatalf("CancelOrder on closed book: expected ErrBookClosed, got %v", err)
	}
}

func TestSnapshotReturnsCopies(t *testing.T) {
	ob := newTestBook()
	if _, err := ob.AddOrder(limitOrder("bid-1", types.Buy, "100", "1")); err != nil {
		t.Fatalf("AddOrder: %v", err)
	}
	if _, err := ob.AddOrder(limitOrder("ask-1", types.Sell, "101", "1")); err != nil {
		t.Fatalf("AddOrder: %v", err)
	}

	snap := ob.GetSnapshot()
	if len(snap.Bids) == 0 || len(snap.Asks) == 0 {
		t.Fatal("snapshot should include bids and asks")
	}

	snap.Bids[0].Price = decimal.RequireFromString("1")
	snap.Asks[0].Price = decimal.RequireFromString("999")

	bids := ob.GetBids()
	if bids[0].Price.Equal(decimal.RequireFromString("1")) {
		t.Fatal("mutating snapshot bids should not change internal book")
	}
	asks := ob.GetAsks()
	if asks[0].Price.Equal(decimal.RequireFromString("999")) {
		t.Fatal("mutating snapshot asks should not change internal book")
	}
}

func TestGetBidsAndAsksReturnCopies(t *testing.T) {
	ob := newTestBook()
	if _, err := ob.AddOrder(limitOrder("bid-1", types.Buy, "100", "1")); err != nil {
		t.Fatalf("AddOrder: %v", err)
	}

	bids := ob.GetBids()
	bids[0].Price = decimal.RequireFromString("1")

	internal := ob.GetBids()
	if internal[0].Price.Equal(decimal.RequireFromString("1")) {
		t.Fatal("mutating returned bid slice should not change internal book")
	}
}
