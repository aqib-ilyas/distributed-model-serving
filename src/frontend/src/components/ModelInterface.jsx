import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

const ModelInterface = () => {
    const [input, setInput] = useState("");
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async () => {
        setIsLoading(true);
        setError(null);
        try {
            // Convert input text to integers
            const encoder = new TextEncoder();
            const inputData = Array.from(encoder.encode(input)).map(Number); // Convert to integers

            const response = await fetch(
                "http://localhost:8000/api/model/process",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    mode: "cors",
                    body: JSON.stringify({
                        data: inputData,
                        metadata: {
                            timestamp: new Date().toISOString(),
                            type: "text_generation",
                        },
                    }),
                }
            );

            if (!response.ok) {
                throw new Error("Failed to process input");
            }

            const data = await response.json();
            // Convert the response data back to text
            const decoder = new TextDecoder();
            const outputText = decoder.decode(new Uint8Array(data.data));
            setResult({
                ...data,
                decodedText: outputText,
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="container mx-auto p-4 max-w-2xl">
            <Card>
                <CardHeader>
                    <CardTitle>Distributed Model Interface</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium mb-2">
                                Input Data
                            </label>
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                className="w-full h-32 p-2 border rounded-md"
                                placeholder="Enter prompt..."
                            />
                        </div>

                        <Button
                            onClick={handleSubmit}
                            disabled={isLoading || !input.trim()}
                            className="w-full"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Processing...
                                </>
                            ) : (
                                "Process Input"
                            )}
                        </Button>

                        {error && (
                            <Alert variant="destructive">
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}

                        {result && (
                            <div className="mt-4">
                                <h3 className="font-medium mb-2">Result:</h3>
                                <div className="bg-gray-100 p-4 rounded-md overflow-auto">
                                    <p>{result.decodedText}</p>
                                </div>

                                <div className="mt-4">
                                    <h4 className="font-medium mb-2">
                                        Processing Details:
                                    </h4>
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                        <div>Nodes Used:</div>
                                        <div>3</div>
                                        <div>Processing Time:</div>
                                        <div>
                                            {result.processingTime || "N/A"} ms
                                        </div>
                                        <div>Output Size:</div>
                                        <div>
                                            {result.data
                                                ? result.data.length
                                                : 0}{" "}
                                            elements
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default ModelInterface;
