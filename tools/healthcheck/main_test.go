package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func testClient(timeout time.Duration) *http.Client {
	return &http.Client{
		Timeout: timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

func statusServer(code int) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(
		func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(code)
		}))
}

func TestRunStatuses(t *testing.T) {
	cases := []struct {
		name string
		code int
		want int
	}{
		{"ok", http.StatusOK, 0},
		{"server error", http.StatusInternalServerError, 1},
		{"not found", http.StatusNotFound, 1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			srv := statusServer(tc.code)
			defer srv.Close()
			var stderr bytes.Buffer
			got := run([]string{srv.URL}, testClient(time.Second), &stderr)
			if got != tc.want {
				t.Fatalf("got %d, want %d", got, tc.want)
			}
		})
	}
}

func TestRunRedirectNotFollowed(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/ok", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/redirect", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/ok", http.StatusMovedPermanently)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()
	var stderr bytes.Buffer
	got := run([]string{srv.URL + "/redirect"}, testClient(time.Second), &stderr)
	if got != 1 {
		t.Fatalf("got %d, want 1", got)
	}
}

func TestRunConnectionRefused(t *testing.T) {
	srv := statusServer(http.StatusOK)
	url := srv.URL
	srv.Close()
	var stderr bytes.Buffer
	if got := run([]string{url}, testClient(time.Second), &stderr); got != 1 {
		t.Fatalf("got %d, want 1", got)
	}
}

func TestRunNoArguments(t *testing.T) {
	var stderr bytes.Buffer
	if got := run(nil, testClient(time.Second), &stderr); got != 1 {
		t.Fatalf("got %d, want 1", got)
	}
	if stderr.Len() == 0 {
		t.Fatal("expected usage message")
	}
}

func TestRunInvalidURL(t *testing.T) {
	for _, arg := range []string{"://bad", "not a url", "ftp://example.com", "http://"} {
		var stderr bytes.Buffer
		if got := run([]string{arg}, testClient(time.Second), &stderr); got != 1 {
			t.Fatalf("%q: got %d, want 1", arg, got)
		}
	}
}

func TestRunTimeout(t *testing.T) {
	release := make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(
		func(w http.ResponseWriter, r *http.Request) {
			select {
			case <-release:
			case <-r.Context().Done():
			}
		}))
	defer srv.Close()
	defer close(release)
	var stderr bytes.Buffer
	got := run([]string{srv.URL}, testClient(50*time.Millisecond), &stderr)
	if got != 1 {
		t.Fatalf("got %d, want 1", got)
	}
}
