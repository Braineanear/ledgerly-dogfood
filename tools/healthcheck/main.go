// Command healthcheck GETs a URL and exits 0 only on HTTP 200.
package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"time"
)

func run(args []string, client *http.Client, stderr io.Writer) int {
	if len(args) < 1 || args[0] == "" {
		fmt.Fprintln(stderr, "usage: healthcheck URL")
		return 1
	}
	u, err := url.Parse(args[0])
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		fmt.Fprintf(stderr, "healthcheck: invalid URL %q\n", args[0])
		return 1
	}
	resp, err := client.Get(u.String())
	if err != nil {
		fmt.Fprintf(stderr, "healthcheck: %v\n", err)
		return 1
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	if resp.StatusCode != http.StatusOK {
		fmt.Fprintf(stderr, "healthcheck: unexpected status %d\n", resp.StatusCode)
		return 1
	}
	return 0
}

func main() {
	client := &http.Client{
		Timeout: 5 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	os.Exit(run(os.Args[1:], client, os.Stderr))
}
