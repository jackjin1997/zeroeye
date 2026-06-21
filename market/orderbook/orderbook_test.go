package orderbook

import (
	"testing"

	"github.com/shopspring/decimal"
	"github.com/tent-of-trials/market/types"
)

func TestOrderBook_CancelBidOrder(t *testing.T) {
	symbol := types.Symbol("BTCUSD")
	config := Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 4,
	}
	ob := NewOrderBook(symbol, config)

	order := &types.Order{
		ID:           "order-1",
		Symbol:       symbol,
		Side:         types.Buy,
		Type:         types.Limit,
		Price:        decimal.NewFromFloat(50000.0),
		RemainingQty: decimal.NewFromFloat(1.5),
	}

	_, err := ob.AddOrder(order)
	if err != nil {
		t.Fatalf("failed to add order: %v", err)
	}

	// Verify order exists in the book's internal orders map
	ob.mu.RLock()
	_, exists := ob.orders["order-1"]
	ob.mu.RUnlock()
	if !exists {
		t.Fatalf("order not registered in internal map")
	}

	// Verify bid level is present
	bids := ob.GetBids()
	if len(bids) != 1 || !bids[0].Price.Equal(order.Price) {
		t.Fatalf("expected bid level at %v", order.Price)
	}

	// Cancel the order
	err = ob.CancelOrder("order-1")
	if err != nil {
		t.Fatalf("failed to cancel order: %v", err)
	}

	// Verify order ID is deleted from internal orders map
	ob.mu.RLock()
	_, exists = ob.orders["order-1"]
	ob.mu.RUnlock()
	if exists {
		t.Fatalf("expected order to be deleted from internal orders map")
	}

	// Verify bid level is removed
	bids = ob.GetBids()
	if len(bids) != 0 {
		t.Fatalf("expected bids to be empty, got %d levels", len(bids))
	}
}

func TestOrderBook_CancelAskOrder(t *testing.T) {
	symbol := types.Symbol("BTCUSD")
	config := Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 4,
	}
	ob := NewOrderBook(symbol, config)

	order := &types.Order{
		ID:           "order-2",
		Symbol:       symbol,
		Side:         types.Sell,
		Type:         types.Limit,
		Price:        decimal.NewFromFloat(51000.0),
		RemainingQty: decimal.NewFromFloat(2.0),
	}

	_, err := ob.AddOrder(order)
	if err != nil {
		t.Fatalf("failed to add order: %v", err)
	}

	// Verify ask level is present
	asks := ob.GetAsks()
	if len(asks) != 1 || !asks[0].Price.Equal(order.Price) {
		t.Fatalf("expected ask level at %v", order.Price)
	}

	// Cancel the order
	err = ob.CancelOrder("order-2")
	if err != nil {
		t.Fatalf("failed to cancel order: %v", err)
	}

	// Verify ask level is removed
	asks = ob.GetAsks()
	if len(asks) != 0 {
		t.Fatalf("expected asks to be empty, got %d levels", len(asks))
	}
}

func TestOrderBook_CancelUnknownOrder(t *testing.T) {
	symbol := types.Symbol("BTCUSD")
	config := Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 4,
	}
	ob := NewOrderBook(symbol, config)

	err := ob.CancelOrder("unknown-order")
	if err != ErrOrderNotFound {
		t.Fatalf("expected ErrOrderNotFound, got %v", err)
	}
}

func TestOrderBook_ClosedBook(t *testing.T) {
	symbol := types.Symbol("BTCUSD")
	config := Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 4,
	}
	ob := NewOrderBook(symbol, config)
	ob.Close()

	// Try adding order
	order := &types.Order{
		ID:           "order-3",
		Symbol:       symbol,
		Side:         types.Buy,
		Price:        decimal.NewFromFloat(50000.0),
		RemainingQty: decimal.NewFromFloat(1.0),
	}
	_, err := ob.AddOrder(order)
	if err != ErrBookClosed {
		t.Fatalf("expected ErrBookClosed, got %v", err)
	}

	// Try cancelling order
	err = ob.CancelOrder("order-3")
	if err != ErrBookClosed {
		t.Fatalf("expected ErrBookClosed, got %v", err)
	}
}

func TestOrderBook_SnapshotImmutability(t *testing.T) {
	symbol := types.Symbol("BTCUSD")
	config := Config{
		MaxDepth:       10,
		PriceDecimals:  2,
		VolumeDecimals: 4,
	}
	ob := NewOrderBook(symbol, config)

	orderBid := &types.Order{
		ID:           "bid-1",
		Symbol:       symbol,
		Side:         types.Buy,
		Price:        decimal.NewFromFloat(50000.0),
		RemainingQty: decimal.NewFromFloat(1.0),
	}
	orderAsk := &types.Order{
		ID:           "ask-1",
		Symbol:       symbol,
		Side:         types.Sell,
		Price:        decimal.NewFromFloat(51000.0),
		RemainingQty: decimal.NewFromFloat(1.0),
	}

	if _, err := ob.AddOrder(orderBid); err != nil {
		t.Fatalf("failed to add bid order: %v", err)
	}
	if _, err := ob.AddOrder(orderAsk); err != nil {
		t.Fatalf("failed to add ask order: %v", err)
	}


	snapshot := ob.GetSnapshot()

	// Mutate returned slice
	snapshot.Bids[0].Price = decimal.NewFromFloat(999999.0)
	snapshot.Asks[0].Price = decimal.NewFromFloat(111111.0)

	// Fetch another snapshot and verify it was not modified
	newSnapshot := ob.GetSnapshot()
	if newSnapshot.Bids[0].Price.Equal(decimal.NewFromFloat(999999.0)) {
		t.Fatalf("snapshot mutation affected internal order book bids state")
	}
	if newSnapshot.Asks[0].Price.Equal(decimal.NewFromFloat(111111.0)) {
		t.Fatalf("snapshot mutation affected internal order book asks state")
	}

	// Verify GetBids() / GetAsks() copy slices
	bids := ob.GetBids()
	bids[0] = nil
	newBids := ob.GetBids()
	if newBids[0] == nil {
		t.Fatalf("GetBids mutation affected internal order book state")
	}
}
