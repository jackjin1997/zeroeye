// orderbook_test.go

package orderbook

import (
	"testing"
)

func TestCancelBid(t *testing.T) {
	ob := NewOrderBook()
	orderID := ob.AddBid(100, 1)
	ob.CancelOrder(orderID)

	if _, exists := ob.bids[orderID]; exists {
		t.Fatalf("expected bid to be removed, but it still exists")
	}
}

func TestCancelAsk(t *testing.T) {
	ob := NewOrderBook()
	orderID := ob.AddAsk(100, 1)
	ob.CancelOrder(orderID)

	if _, exists := ob.asks[orderID]; exists {
		t.Fatalf("expected ask to be removed, but it still exists")
	}
}

func TestCancelUnknownOrder(t *testing.T) {
	ob := NewOrderBook()
	err := ob.CancelOrder("unknownID")

	if err != ErrOrderNotFound {
		t.Fatalf("expected ErrOrderNotFound, got %v", err)
	}
}

func TestClosedBookRejectsOperations(t *testing.T) {
	ob := NewOrderBook()
	ob.Close()
	err := ob.AddBid(100, 1)

	if err != ErrBookClosed {
		t.Fatalf("expected ErrBookClosed, got %v", err)
	}
}

func TestSnapshotImmutability(t *testing.T) {
	ob := NewOrderBook()
	ob.AddBid(100, 1)
	snapshot := ob.Snapshot()

	snapshot.Bids[0].Price = 200 // Attempt to mutate snapshot

	if ob.bids[1].Price == 200 {
		t.Fatalf("expected internal bids to be immutable")
	}
}
